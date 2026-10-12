"""First native, networked neural-layer pipeline: signed, bounded numeric inference.

This deliberately tiny model demonstrates a single forward pass partitioned
between independently running machines. It is NOT an LLM/transformer shard.
"""
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .client import post
from .crypto import identity_id, load_identity, signed, verify

MAX_D=256


def _vector(value):
    if not isinstance(value,list) or not 1<=len(value)<=MAX_D:
        raise ValueError('Invalid activation dimensions')
    if not all(isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x) and abs(x)<=1e6 for x in value):
        raise ValueError('Invalid numeric activation')
    return [float(x) for x in value]


class DenseLayer:
    def __init__(self,weights,bias,activation='relu'):
        if activation not in ('relu','linear','tanh'):
            raise ValueError('Unknown layer activation')
        if not isinstance(weights,list) or not 1<=len(weights)<=MAX_D:
            raise ValueError('Invalid matrix output width')
        cols=None
        normalized=[]
        for row in weights:
            data=_vector(row)
            if cols is not None and len(data)!=cols:
                raise ValueError('Non-rectangular weight matrix')
            cols=len(data)
            normalized.append(data)
        if not isinstance(bias,list) or len(bias)!=len(normalized):
            raise ValueError('Invalid bias width')
        self.bias=_vector(bias)
        self.weights=normalized
        self.activation=activation

    @classmethod
    def from_file(cls,path):
        obj=json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(obj['weights'],obj['bias'],obj.get('activation','relu'))

    def forward(self,x):
        x=_vector(x)
        if len(x)!=len(self.weights[0]):
            raise ValueError('Activation dimension does not match stage')
        results=[]
        for row,bias in zip(self.weights,self.bias):
            z=math.fsum(a*b for a,b in zip(row,x))+bias
            if not math.isfinite(z) or abs(z)>1e9:
                raise ValueError('Unbounded activation')
            results.append(max(0,z) if self.activation=='relu' else
                           math.tanh(z) if self.activation=='tanh' else z)
        return results


def pipeline(urls,identity_path,input_vector):
    current=_vector(input_vector)
    identity=load_identity(identity_path)
    if not urls or len(urls)>32:
        raise ValueError('Expected 1-32 explicitly configured layer endpoints')
    for url in urls:
        result=post(url,'/v2/tensor/forward',signed(identity,'tensor.forward',{'input':current}),timeout=10)
        current=_vector(result['output'])
    return current


def pipeline_redundant(stages,identity_path,input_vector,verify_replicas=False):
    """Layerwise forward pass with explicit redundant consenting hosts per stage.

    stages = [[primary_url, optional_backup_url], [next_layer_url], ...].
    Every alternative in a stage MUST hold identical operator-approved weights.
    """
    current=_vector(input_vector)
    identity=load_identity(identity_path)
    if not isinstance(stages,list) or not 1<=len(stages)<=32:
        raise ValueError('Expected 1-32 neural stages')
    for alternatives in stages:
        if not isinstance(alternatives,list) or not 1<=len(alternatives)<=6:
            raise ValueError('Each stage needs 1-6 allowed replicas')
        errors=[]
        received=[]
        if verify_replicas and len(alternatives)<3:
            raise ValueError('Verified mode requires at least 3 independent donors per stage')
        for url in alternatives:
            try:
                result=post(url,'/v2/tensor/forward',
                            signed(identity,'tensor.forward',{'input':current}),timeout=1.5)
                values=_vector(result['output'])
                if verify_replicas:
                    received.append(values)
                    if any(len(values)==len(prior) and all(math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-10) for a,b in zip(values,prior)) for prior in received[:-1]):
                        current=values
                        break
                else:
                    current=values
                    break
            except (OSError,RuntimeError,ValueError) as exc:
                errors.append(type(exc).__name__)
        else:
            raise RuntimeError('Insufficient matching volunteer responses for stage: '+', '.join(errors))
    return current


def make_layer_server(layer,allowed_public_keys,host='127.0.0.1',port=0):
    # Trusted client public identities are installed out-of-band by volunteers.
    allowed={}
    for obj in allowed_public_keys:
        if not all(isinstance(obj.get(k),str) for k in ('id','public')):
            raise ValueError('Invalid accepted client identity')
        if identity_id(obj['public'])!=obj['id']:
            raise ValueError('Untrusted client key')
        allowed[obj['id']]=obj['public']
    if not allowed:
        raise ValueError('No authorized compute clients')
    seen=set()
    from threading import RLock
    lock=RLock()

    class Handler(BaseHTTPRequestHandler):
        def reply(self,code,obj):
            out=json.dumps(obj).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def do_POST(self):
            if self.path!='/v2/tensor/forward':return self.reply(404,{'error':'Not found'})
            try:
                sz=int(self.headers.get('Content-Length','0'))
                if not 0<sz<=8192:return self.reply(413,{'error':'Size limit'})
                envelope=json.loads(self.rfile.read(sz))
                ident=verify(envelope,'tensor.forward')
                if allowed.get(ident)!=envelope['public']:
                    raise PermissionError('Unrecognized pipeline client')
                with lock:
                    marker=(ident,envelope['nonce'])
                    if marker in seen:raise PermissionError('Replay')
                    if len(seen)>=4096:seen.clear()
                    seen.add(marker)
                body=envelope['body']
                return self.reply(200,{'output':layer.forward(body['input'])})
            except PermissionError as exc:return self.reply(403,{'error':str(exc)[:120]})
            except (ValueError,KeyError,TypeError) as exc:return self.reply(400,{'error':str(exc)[:120]})
        def log_message(self,*args):pass

    return ThreadingHTTPServer((host,port),Handler)
