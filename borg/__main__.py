"""User-facing CLI: python -m borg --help"""
import argparse
import json
import os
from pathlib import Path
from .crypto import create_identity, load_identity
from .store import Store
from .http import make_server
from . import client
from .models import infer
from .mesh import public_identity, sync
from .mission import run_mission
from .quorum import QuorumNode
from .quorum_http import make_quorum_server
from .brain import open_workspace, remote_state, remote_propose, model_contribute, model_decide
from .tensor import DenseLayer,make_layer_server,pipeline_redundant
from .volunteer import donate as volunteer_donate
from .away import create as away_create, contribute as away_contribute, merge as away_merge, return_payload as away_return_payload, load as away_load, save as away_save, validate as away_validate


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
        p.add_argument("--backend",choices=("mock","gguf","ollama","http-api","openai-compatible"),default="mock")
        p.add_argument("--model")
        p.add_argument("--base-url")

    p=add("init");storage(p);p.add_argument("--collective-id",help="Use existing collective ID for a new invited node")
    p=add("serve");storage(p);p.add_argument("--port",type=int,default=8787);p.add_argument("--identity",help="Node identity key enables signed mesh connections")
    p=add("identity");p.add_argument("--out",required=True);p.add_argument("--name",required=True)
    p=add("identity-public");identity(p);p.add_argument("--out",required=True)
    p=add("mesh-trust");storage(p);p.add_argument("--public-file",required=True)
    p=add("mesh-sync");storage(p);identity(p);url(p);p.add_argument("--watch",action="store_true");p.add_argument("--interval",type=int,default=30)
    p=add("peer-join");url(p);identity(p)
    p=add("ask");url(p);identity(p);p.add_argument("prompt");p.add_argument("--share-with-volunteers",action="store_true");p.add_argument("--share-with-collective",action="store_true")
    p=add("status");url(p);identity(p);p.add_argument("request_id")
    p=add("node-join");url(p);identity(p);p.add_argument("--trusted",action="store_true")
    p=add("worker");url(p);identity(p);backend(p);p.add_argument("--once",action="store_true");p.add_argument("--max-jobs",type=int,default=0)
    p=add("mission-new");storage(p);p.add_argument("title");p.add_argument("brief");p.add_argument("--out",required=True)
    p=add("mission-work");backend(p);p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    p=add("mission-import");storage(p);p.add_argument("--input",required=True)
    p=add("verify");storage(p)
    # V1.1: pinned collective cognitive quorum. Technical quorum != governance.
    p=add('cluster-config');p.add_argument('--collective-id',required=True);p.add_argument('--node',action='append',required=True,help='PUBLIC_IDENTITY_JSON=URL');p.add_argument('--out',required=True)
    for name in ('cluster-serve','cluster-elect','cluster-ping','cluster-grant','cluster-audit'):
        p=add(name);p.add_argument('--db',required=True);p.add_argument('--key',required=True);p.add_argument('--config',required=True)
        if name=='cluster-serve':p.add_argument('--port',type=int,required=True)
        if name=='cluster-grant':p.add_argument('--public-file',required=True)
    p=add('brain-open');url(p);identity(p);p.add_argument('question');p.add_argument('--goal',required=True)
    p=add('brain-show');url(p);identity(p);p.add_argument('--workspace-id')
    p=add('brain-contribute');url(p);identity(p);p.add_argument('workspace_id');p.add_argument('--role',choices=('explore','challenge','verify','research','compute'),required=True);p.add_argument('--content');backend(p)
    p=add('brain-decide');url(p);identity(p);p.add_argument('workspace_id');p.add_argument('--content');backend(p)
    p=add('brain-mission');url(p);identity(p);p.add_argument('brief');p.add_argument('--member',action='append',default=[],help='Approved crew identity ID')
    p=add('brain-mission-return');url(p);identity(p);p.add_argument('--bundle',required=True);p.add_argument('--report',required=True)
    p=add('away-create');url(p);identity(p);p.add_argument('--mission-id',required=True);p.add_argument('--crew-public',action='append',required=True);p.add_argument('--out',required=True)
    p=add('away-add');p.add_argument('--input',required=True);p.add_argument('--out',required=True);identity(p);p.add_argument('--role',choices=('explore','challenge','verify','research','compute'),required=True);p.add_argument('--content',required=True)
    p=add('away-merge');p.add_argument('--input',action='append',required=True);p.add_argument('--out',required=True)
    p=add('away-verify');p.add_argument('--input',required=True)
    p=add('tensor-serve');p.add_argument('--weights',required=True);p.add_argument('--allow-client',action='append',required=True,help='Approved PUBLIC_IDENTITY_JSON');p.add_argument('--port',type=int,required=True)
    p=add('tensor-run');identity(p);p.add_argument('--stage',action='append',required=True,help='Comma-separated redundant URLs for one layer');p.add_argument('--input',required=True,help='JSON numeric vector');p.add_argument('--verify-replicas',action='store_true')
    p=add('volunteer');url(p);identity(p);p.add_argument('--model',required=True,help='Owned/approved GGUF weights');p.add_argument('--threads',type=int,default=1);p.add_argument('--minutes',type=int,default=30);p.add_argument('--max-jobs',type=int,default=10);p.add_argument('--max-ram-mb',type=int);p.add_argument('--gpu-layers',type=int,default=0);p.add_argument('--consent',action='store_true')

    args=parser.parse_args()
    if args.command=='cluster-config':
        nodes=[]
        for item in args.node:
            filename,sep,endpoint=item.partition('=')
            if not sep or not filename or not endpoint:raise SystemExit('Node argument must be PUBLIC_FILE=URL')
            obj=json.loads(Path(filename).read_text())
            nodes.append({'id':obj['id'],'public':obj['public'],'url':endpoint})
        obj={'collective_id':args.collective_id,'nodes':nodes}
        from .quorum import config_load
        Path(args.out).write_text(json.dumps(obj,indent=2))
        config_load(args.out)
        show({'cluster_config':args.out,'nodes':len(nodes)})
    elif args.command in ('cluster-serve','cluster-elect','cluster-ping','cluster-grant','cluster-audit'):
        node=QuorumNode(args.db,args.key,args.config)
        if args.command=='cluster-serve':
            server=make_quorum_server(node,port=args.port)
            print(f'Borg cognitive replica on http://127.0.0.1:{args.port} (loopback only)',flush=True)
            try:server.serve_forever()
            except KeyboardInterrupt:pass
            finally:server.server_close()
        elif args.command=='cluster-elect':show(node.campaign())
        elif args.command=='cluster-ping':show(node.heartbeat())
        elif args.command=='cluster-audit':show(node.audit())
        else:show({'admitted_actor':node.admit_actor(json.loads(Path(args.public_file).read_text()))})
    elif args.command=='brain-open':show(open_workspace(args.url,args.identity,args.question,args.goal))
    elif args.command=='brain-show':
        state=remote_state(args.url,args.identity)
        show(state['workspaces'].get(args.workspace_id) if args.workspace_id else state)
    elif args.command=='brain-contribute':
        if args.content is not None:
            w=remote_state(args.url,args.identity)['workspaces'][args.workspace_id]
            show(remote_propose(args.url,args.identity,'workspace.contribute',{
                'id':args.workspace_id,'role':args.role,'content':args.content,'expected_revision':w['revision']}))
        else:show(model_contribute(args.url,args.identity,args.workspace_id,args.role,args.backend,args.model,args.base_url))
    elif args.command=='brain-decide':
        if args.content is not None:
            w=remote_state(args.url,args.identity)['workspaces'][args.workspace_id]
            show(remote_propose(args.url,args.identity,'workspace.decide',{
                'id':args.workspace_id,'content':args.content,'expected_revision':w['revision']}))
        else:show(model_decide(args.url,args.identity,args.workspace_id,args.backend,args.model,args.base_url))
    elif args.command=='brain-mission':
        import uuid
        state=remote_state(args.url,args.identity)
        mid='away-'+uuid.uuid4().hex
        show({'mission_id':mid,**remote_propose(args.url,args.identity,'mission.detach',{
             'id':mid,'brief':args.brief,'base':state['commit'],'members':args.member})})
    elif args.command=='brain-mission-return':
        payload=away_return_payload(away_load(args.bundle),args.report)
        show(remote_propose(args.url,args.identity,'mission.return',payload))
    elif args.command=='away-create':
        state=remote_state(args.url,args.identity)
        m=state['missions'][args.mission_id]
        crew=[json.loads(Path(x).read_text()) for x in args.crew_public]
        if set(x['id'] for x in crew)!=set(m['members']):
            raise SystemExit('Public identity roster differs from the detached mission')
        data=away_create(state['collective_id'],args.mission_id,m['base'],m['brief'],crew)
        show({'file':away_save(args.out,data),'crew':len(crew)})
    elif args.command=='away-add':
        show({'file':away_save(args.out,away_contribute(away_load(args.input),args.identity,args.role,args.content))})
    elif args.command=='away-merge':
        if len(args.input)<2:raise SystemExit('Two or more away files required')
        data=away_load(args.input[0])
        for path in args.input[1:]:data=away_merge(data,away_load(path))
        show({'file':away_save(args.out,data),'entries':len(data['entries'])})
    elif args.command=='away-verify':show(away_validate(away_load(args.input)))
    elif args.command=='tensor-serve':
        layer=DenseLayer.from_file(args.weights)
        allowed=[json.loads(Path(x).read_text()) for x in args.allow_client]
        server=make_layer_server(layer,allowed,port=args.port)
        print(f'Borg numeric layer server at 127.0.0.1:{args.port}',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()
    elif args.command=='tensor-run':
        stages=[s.split(',') for s in args.stage]
        show({'output':pipeline_redundant(stages,args.identity,json.loads(args.input),verify_replicas=args.verify_replicas)})
    elif args.command=='volunteer':
        token=os.getenv('BORG_ADMISSION_TOKEN')
        show(volunteer_donate(args.url,args.identity,token,model=args.model,
             threads=args.threads,max_minutes=args.minutes,max_jobs=args.max_jobs,
             max_ram_mb=args.max_ram_mb,gpu_layers=args.gpu_layers,consent=args.consent))
    elif args.command=="init":

        s=Store(args.db,collective_id=args.collective_id);show({"collective_id":s.collective_id(),"db":args.db})
    elif args.command=="serve":
        token=os.getenv("BORG_ADMISSION_TOKEN")
        if not token: print("Notice: donor admission disabled. Set BORG_ADMISSION_TOKEN before starting if donors will join.")
        trusted_token=os.getenv("BORG_TRUSTED_WORKER_TOKEN")
        http=make_server("127.0.0.1",args.port,args.db,token,trusted_token,identity_path=args.identity)
        print(f"Borg V1 serving at http://127.0.0.1:{args.port} (loopback only)")
        try:http.serve_forever()
        except KeyboardInterrupt:pass
        finally:http.server_close()
    elif args.command=="identity":show(create_identity(args.out,args.name))
    elif args.command=="identity-public":
        obj=public_identity(load_identity(args.identity))
        Path(args.out).write_text(json.dumps(obj,indent=2))
        show({"public_identity":args.out,"id":obj["id"]})
    elif args.command=="mesh-trust":
        show(Store(args.db).mesh_trust(json.loads(Path(args.public_file).read_text())))
    elif args.command=="mesh-sync":
        import time
        while True:
            show(sync(Store(args.db),load_identity(args.identity),args.url))
            if not args.watch: break
            time.sleep(max(args.interval,5))
    elif args.command=="peer-join":show(client.peer_join(args.url,args.identity))
    elif args.command=="ask":show(client.ask(args.url,args.identity,args.prompt,args.share_with_volunteers,args.share_with_collective))
    elif args.command=="status":show(client.status(args.url,args.identity,args.request_id))
    elif args.command=="node-join":
        token=os.getenv("BORG_ADMISSION_TOKEN")
        if not token:raise SystemExit("Set BORG_ADMISSION_TOKEN to the server's admission token")
        trusted_token=os.getenv("BORG_TRUSTED_WORKER_TOKEN")
        if args.trusted and not trusted_token:
            raise SystemExit("Trusted workers require BORG_TRUSTED_WORKER_TOKEN")
        show(client.node_join(args.url,args.identity,token,args.trusted,trusted_token))
    elif args.command=="worker":
        kw={"backend":args.backend,"model":args.model,"base_url":args.base_url}
        if args.once:show(client.work_once(args.url,args.identity,**kw) or {"job":None})
        else:show({"completed":client.work_loop(args.url,args.identity,max_jobs=args.max_jobs,**kw)})
    elif args.command=="mission-new":
        obj=Store(args.db).create_mission(args.title,args.brief)
        Path(args.out).write_text(json.dumps(obj,indent=2));show(obj)
    elif args.command=="mission-work":
        obj=json.loads(Path(args.input).read_text())
        report=run_mission(obj,args.backend,args.model,args.base_url)
        Path(args.out).write_text(json.dumps(report,indent=2));show({"report_saved":args.out,"crew":list(report["crew_results"])})
    elif args.command=="mission-import":show(Store(args.db).import_mission(json.loads(Path(args.input).read_text())))
    elif args.command=="verify":show({"history_valid":Store(args.db).history()})


if __name__=="__main__":main()
