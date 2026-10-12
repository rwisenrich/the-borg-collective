"""User-facing CLI: python -m borg --help"""
import argparse
import json
import os
from pathlib import Path
from .crypto import create_identity
from .store import Store
from .http import make_server
from . import client
from .models import infer


def show(value):
    print(json.dumps(value,indent=2,ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser(prog="borg",description="The Borg Collective V1 (local first)")
    sub=parser.add_subparsers(dest="command",required=True)
    def add(name):return sub.add_parser(name)
    def url(p):p.add_argument("--url",default="http://127.0.0.1:8787")
    def identity(p):p.add_argument("--identity",required=True)
    def storage(p):p.add_argument("--db",default="borg.sqlite3")
    def backend(p):
        p.add_argument("--backend",choices=("mock","ollama","openai-compatible"),default="mock")
        p.add_argument("--model")
        p.add_argument("--base-url")

    p=add("init");storage(p)
    p=add("serve");storage(p);p.add_argument("--port",type=int,default=8787)
    p=add("identity");p.add_argument("--out",required=True);p.add_argument("--name",required=True)
    p=add("peer-join");url(p);identity(p)
    p=add("ask");url(p);identity(p);p.add_argument("prompt");p.add_argument("--share-with-volunteers",action="store_true");p.add_argument("--share-with-collective",action="store_true")
    p=add("status");url(p);identity(p);p.add_argument("request_id")
    p=add("node-join");url(p);identity(p);p.add_argument("--trusted",action="store_true")
    p=add("worker");url(p);identity(p);backend(p);p.add_argument("--once",action="store_true");p.add_argument("--max-jobs",type=int,default=0)
    p=add("mission-new");storage(p);p.add_argument("title");p.add_argument("brief");p.add_argument("--out",required=True)
    p=add("mission-work");backend(p);p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    p=add("mission-import");storage(p);p.add_argument("--input",required=True)
    p=add("verify");storage(p)
    args=parser.parse_args()
    if args.command=="init":
        s=Store(args.db);show({"collective_id":s.collective_id(),"db":args.db})
    elif args.command=="serve":
        token=os.getenv("BORG_ADMISSION_TOKEN")
        if not token: print("Notice: donor admission disabled. Set BORG_ADMISSION_TOKEN before starting if donors will join.")
        http=make_server("127.0.0.1",args.port,args.db,token)
        print(f"Borg V1 serving at http://127.0.0.1:{args.port} (loopback only)")
        try:http.serve_forever()
        except KeyboardInterrupt:pass
        finally:http.server_close()
    elif args.command=="identity":show(create_identity(args.out,args.name))
    elif args.command=="peer-join":show(client.peer_join(args.url,args.identity))
    elif args.command=="ask":show(client.ask(args.url,args.identity,args.prompt,args.share_with_volunteers,args.share_with_collective))
    elif args.command=="status":show(client.status(args.url,args.identity,args.request_id))
    elif args.command=="node-join":
        token=os.getenv("BORG_ADMISSION_TOKEN")
        if not token:raise SystemExit("Set BORG_ADMISSION_TOKEN to the server's admission token")
        show(client.node_join(args.url,args.identity,token,args.trusted))
    elif args.command=="worker":
        kw={"backend":args.backend,"model":args.model,"base_url":args.base_url}
        if args.once:show(client.work_once(args.url,args.identity,**kw) or {"job":None})
        else:show({"completed":client.work_loop(args.url,args.identity,max_jobs=args.max_jobs,**kw)})
    elif args.command=="mission-new":
        obj=Store(args.db).create_mission(args.title,args.brief)
        Path(args.out).write_text(json.dumps(obj,indent=2));show(obj)
    elif args.command=="mission-work":
        obj=json.loads(Path(args.input).read_text())
        report=infer("Carry out this detached research mission. Return verifiable findings, limitations and uncertainties.\n"+obj["brief"],args.backend,args.model,args.base_url)
        obj["report"]=report
        Path(args.out).write_text(json.dumps(obj,indent=2));show({"report_saved":args.out})
    elif args.command=="mission-import":show(Store(args.db).import_mission(json.loads(Path(args.input).read_text())))
    elif args.command=="verify":show({"history_valid":Store(args.db).history()})


if __name__=="__main__":main()
