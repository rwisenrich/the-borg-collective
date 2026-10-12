"""Signed external AI peers and opt-in volunteered inference workers."""
import json
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from .crypto import load_identity, signed
from .models import infer


def post(base_url, path, envelope, token=None, timeout=30):
    u=urlparse(base_url)
    if u.scheme != "https" and not (u.scheme=="http" and u.hostname in ("127.0.0.1","localhost","::1")):
        raise ValueError("Remote connections require HTTPS; insecure HTTP is loopback-only")
    headers={"Content-Type":"application/json"}
    if token:
        headers["X-Admission-Token"]=token
    req=Request(base_url.rstrip("/")+path,json.dumps(envelope).encode(),headers)
    try:
        with urlopen(req,timeout=timeout) as response:
            return json.load(response)
    except HTTPError as e:
        try: msg=json.loads(e.read()).get("error", "Request failed")
        except Exception: msg="Request failed"
        raise RuntimeError(f"HTTP {e.code}: {msg}") from e


def peer_join(url, path):
    identity=load_identity(path)
    return post(url,"/v1/peers/register",signed(identity,"peer.register",{"name":identity["name"]}))


def ask(url,path,prompt,share_with_volunteers=False,share_with_collective=False):
    identity=load_identity(path)
    return post(url,"/v1/peers/ask",signed(identity,"peer.ask",{"prompt":prompt,"share_with_volunteers":share_with_volunteers,"share_with_collective":share_with_collective}))


def status(url,path,request_id):
    identity=load_identity(path)
    return post(url,"/v1/peers/status",signed(identity,"peer.status",{"request_id":request_id}))


def node_join(url,path,admission_token,trusted=False):
    identity=load_identity(path)
    body={"name":identity["name"],"trusted":trusted}
    return post(url,"/v1/nodes/register",signed(identity,"node.register",body),token=admission_token)


def work_once(url,path,backend="mock",model=None,base_url=None):
    identity=load_identity(path)
    response=post(url,"/v1/nodes/claim",signed(identity,"node.claim",{}))
    job=response.get("job")
    if not job:
        return None
    result=infer(job["prompt"],backend=backend,model=model,base_url=base_url)
    response=post(url,"/v1/nodes/complete",signed(identity,"node.complete",{
        "job_id":job["id"],"lease":job["lease"],"result":result}))
    return response


def work_loop(url,path,backend="mock",model=None,base_url=None,interval=2.0,max_jobs=0):
    n=0
    while max_jobs <= 0 or n < max_jobs:
        finished=work_once(url,path,backend,model,base_url)
        if finished:
            n+=1
            print("Completed",finished["job_id"])
        else:
            time.sleep(interval)
    return n
