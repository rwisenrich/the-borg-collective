"""Explicitly enrolled, signed replica RPC and collective cognition API."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .quorum import QuorumError, QuorumNode


def make_quorum_server(node: QuorumNode, host='127.0.0.1', port=0):
    class Handler(BaseHTTPRequestHandler):
        server_version='BorgQuorum/1.1'

        def respond(self,code,data):
            out=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def do_GET(self):
            if self.path=='/v2/health':
                s=node.status()
                return self.respond(200,{k:s[k] for k in ('node_id','term','commit','last_index')})
            self.respond(404,{'error':'Not found'})

        def do_POST(self):
            if self.path not in ('/v2/quorum/vote','/v2/quorum/append',
                                 '/v2/brain/state','/v2/brain/propose'):
                return self.respond(404,{'error':'Not found'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=65536:
                    return self.respond(413,{'error':'Message too large'})
                env=json.loads(self.rfile.read(size))
                if not isinstance(env,dict):raise ValueError('Signed envelope must be object')
                if self.path=='/v2/quorum/vote':result=node.vote(env)
                elif self.path=='/v2/quorum/append':result=node.append(env)
                elif self.path=='/v2/brain/state':
                    with node.lock,node.tx() as db:
                        node._actor(db,env,'brain.state')
                        result=node._view(db)
                else:
                    body=env.get('body',{})
                    if not isinstance(body,dict):raise ValueError('Invalid proposal')
                    result=node.accept_actor(env,body.get('kind'))
                return self.respond(200,result)
            except PermissionError as exc:
                self.respond(403,{'error':str(exc)[:160]})
            except QuorumError as exc:
                self.respond(409,{'error':str(exc)[:160]})
            except (ValueError,KeyError,TypeError,OverflowError) as exc:
                self.respond(400,{'error':str(exc)[:160]})
            except Exception as exc:
                self.log_error('Node error %s',type(exc).__name__)
                self.respond(500,{'error':'Internal node error'})

        def log_message(self,fmt,*args):
            pass  # never print research prompts or identity envelopes

    return ThreadingHTTPServer((host,port),Handler)
