"""Two different OS processes computing consecutive neural layers with failover."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from borg.crypto import create_identity
from borg.tensor import DenseLayer,pipeline_redundant


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def run():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        private=root/'ai.key'
        public=create_identity(private,'Authorized inference requester')
        pub=root/'ai-public.json'
        pub.write_text(json.dumps(public))
        layers=[{'weights':[[.2,.1],[.6,-.2]],'bias':[.1,.7],'activation':'relu'},
                {'weights':[[.7,.4],[-.3,.1]],'bias':[-.2,.1],'activation':'tanh'}]
        weight_paths=[]
        for i,obj in enumerate(layers):
            f=root/f'layer{i}.json';f.write_text(json.dumps(obj));weight_paths.append(f)
        ports=[port() for _ in range(3)]
        processes=[None]*3
        def start(i,layer_index):
            command=[sys.executable,'-m','borg','tensor-serve','--weights',str(weight_paths[layer_index]),
                     '--allow-client',str(pub),'--port',str(ports[i])]
            processes[i]=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                          env={**os.environ,'PYTHONUNBUFFERED':'1'})
            # Probe real signed service without assuming readiness from a sleeping process.
            from borg.tensor import pipeline
            deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                if processes[i].poll() is not None:raise RuntimeError('Layer process died')
                try:
                    pipeline([f'http://127.0.0.1:{ports[i]}'],private,[1.0,.5])
                    return
                except (OSError,RuntimeError):time.sleep(.05)
            raise TimeoutError('Layer did not start')
        def stop(i):
            if processes[i] is not None:
                processes[i].terminate();processes[i].wait(timeout=3);processes[i]=None
        try:
            start(0,0);start(1,0);start(2,1)
            stages=[[f'http://127.0.0.1:{ports[0]}',f'http://127.0.0.1:{ports[1]}'],
                    [f'http://127.0.0.1:{ports[2]}']]
            inp=[1.2,.5]
            expected=DenseLayer(**layers[1]).forward(DenseLayer(**layers[0]).forward(inp))
            before=pipeline_redundant(stages,private,inp)
            stop(0)
            after=pipeline_redundant(stages,private,inp)
            assert max(abs(a-b) for a,b in zip(expected,before))<1e-12
            assert max(abs(a-b) for a,b in zip(expected,after))<1e-12
            return {'passed':True,'stage_count':2,'workers':3,'primary_worker_terminated':True,
                    'redundant_worker_took_over':True,'output':after}
        finally:
            for i in range(3):stop(i)


if __name__=='__main__':print(json.dumps(run(),indent=2))
