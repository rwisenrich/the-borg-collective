"""End-to-end crash-failover demonstration using three separate Python processes.

Runs only on localhost, uses ephemeral keys, and leaves no service running.
No AI model weights are needed: contributions are deterministic test content.
"""
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
from borg.quorum import QuorumNode
from borg.mesh import public_identity
from borg.crypto import load_identity
from borg.brain import open_workspace, remote_propose, remote_state


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def run():
    with tempfile.TemporaryDirectory() as tmp:
        home=Path(tmp)
        ports=[port() for _ in range(3)]
        keys=[]
        nodes=[]
        for i in range(3):
            path=home/f'node{i}.key'
            public=create_identity(path,'Replica '+str(i))
            keys.append(path)
            nodes.append({'id':public['id'],'public':public['public'],
                          'url':f'http://127.0.0.1:{ports[i]}'})
        config=home/'config.json'
        config.write_text(json.dumps({'collective_id':'borg-v1.1-smoke','nodes':nodes}))
        databases=[home/f'n{i}.sqlite3' for i in range(3)]
        replicas=[QuorumNode(databases[i],keys[i],config,timeout=.6) for i in range(3)]
        ai=home/'outside.key'
        create_identity(ai,'Independent contributor')
        child=[None,None,None]
        def start(i):
            command=[sys.executable,'-m','borg','cluster-serve','--db',str(databases[i]),
                     '--key',str(keys[i]),'--config',str(config),'--port',str(ports[i])]
            child[i]=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                                      env={**os.environ,'PYTHONUNBUFFERED':'1'})
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                if child[i].poll() is not None:
                    raise RuntimeError('Replica exited unexpectedly '+str(i))
                try:
                    with urlopen(f'http://127.0.0.1:{ports[i]}/v2/health',timeout=.2) as response:
                        if response.status==200:return
                except (OSError,TimeoutError):time.sleep(.05)
            raise TimeoutError('Replica did not become ready')
        def stop(i):
            if child[i] is not None:
                child[i].terminate()
                try:child[i].wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child[i].kill();child[i].wait(timeout=3)
                if child[i].stderr:child[i].stderr.close()
                child[i]=None
        try:
            for i in range(3):start(i)
            replicas[0].campaign()
            replicas[0].admit_actor(public_identity(load_identity(ai)))
            url_a=f'http://127.0.0.1:{ports[0]}'
            task=open_workspace(url_a,ai,'Can this state survive a worker crash?',
                                'One continuous replicated reasoning process')
            mid=task['workspace_id']
            remote_propose(url_a,ai,'workspace.contribute',{
                'id':mid,'role':'explore','content':'First signed, committed contribution.',
                'expected_revision':1})
            before=replicas[2].view()['workspaces'][mid]
            assert len(before['contributions'])==1
            stop(0)
            replicas[1].campaign()
            url_b=f'http://127.0.0.1:{ports[1]}'
            remote_propose(url_b,ai,'workspace.contribute',{
                'id':mid,'role':'verify','content':'Quorum survived original coordinator loss.',
                'expected_revision':2})
            remote_propose(url_b,ai,'workspace.decide',{
                'id':mid,'content':'Verified: committed state continues across process failure.',
                'expected_revision':3})
            start(0)
            replicas[1].heartbeat()
            states=[replicas[i].view() for i in range(3)]
            assert states[0]==states[1]==states[2]
            assert states[0]['workspaces'][mid]['decision']['content'].startswith('Verified')
            return {'passed':True,'processes':3,'coordinator_killed':True,
                    'replicas_in_agreement':3,'committed':states[0]['commit'],
                    'workspace_id':mid,'decision':states[0]['workspaces'][mid]['decision']['content']}
        finally:
            for i in range(3):stop(i)


if __name__=='__main__':
    print(json.dumps(run(),indent=2))
