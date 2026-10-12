import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from borg.crypto import create_identity, load_identity, signed
from borg.mesh import public_identity
from borg.brain import open_workspace, remote_propose, remote_state
from borg.quorum import QuorumNode, QuorumError
from borg.quorum_http import make_quorum_server
from borg.client import post


def unused_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


class Cluster(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base=Path(self.tmp.name)
        self.paths=[]
        self.ports=[unused_port() for _ in range(3)]
        cluster=[]
        for i in range(3):
            key=base/f'node{i}.key'
            self.paths.append(key)
            ident=create_identity(key,f'Node {i}')
            cluster.append({'id':ident['id'],'public':ident['public'],
                            'url':f'http://127.0.0.1:{self.ports[i]}'})
        self.config=base/'nodes.json'
        self.config.write_text(json.dumps({'collective_id':'borg-test-cluster','nodes':cluster}))
        self.nodes=[QuorumNode(base/f'node{i}.db',self.paths[i],self.config,timeout=.45) for i in range(3)]
        self.server=[None,None,None]
        self.thread=[None,None,None]
        for i in range(3):self.start(i)
        self.user=base/'independent.key'
        create_identity(self.user,'Independent AI')

    def start(self,i):
        self.server[i]=make_quorum_server(self.nodes[i],port=self.ports[i])
        self.thread[i]=threading.Thread(target=self.server[i].serve_forever,daemon=True)
        self.thread[i].start()

    def stop(self,i):
        if self.server[i] is not None:
            self.server[i].shutdown()
            self.server[i].server_close()
            self.thread[i].join(timeout=3)
            self.server[i]=None

    def tearDown(self):
        for i in range(3):self.stop(i)

    def approved(self):
        self.nodes[0].admit_actor(public_identity(load_identity(self.user)))

    def test_one_working_mind_across_three_nodes(self):
        self.nodes[0].campaign()
        self.approved()
        url=f'http://127.0.0.1:{self.ports[0]}'
        result=open_workspace(url,self.user,'Explain the shared mind','A testable design')
        mid=result['workspace_id']
        before=remote_state(url,self.user)['workspaces'][mid]
        self.assertEqual(before['revision'],1)
        remote_propose(url,self.user,'workspace.contribute',{
            'id':mid,'role':'explore','content':'First contribution',
            'expected_revision':1})
        # An outdated state cannot overwrite someone else's recent contribution.
        with self.assertRaises(RuntimeError):
            remote_propose(url,self.user,'workspace.contribute',{
                'id':mid,'role':'verify','content':'Stale contribution',
                'expected_revision':1})
        remote_propose(url,self.user,'workspace.decide',{
            'id':mid,'content':'One collective answer','expected_revision':2})
        for node in self.nodes:
            w=node.view()['workspaces'][mid]
            self.assertEqual(w['decision']['content'],'One collective answer')
            self.assertEqual(w['revision'],3)
            self.assertEqual(node.view()['commit'],4)  # actor grant + 3 operations

    def test_coordinator_failure_resumes_on_survivors(self):
        self.nodes[0].campaign()
        self.approved()
        mid='mind-failover'
        self.nodes[0].propose('workspace.open',{
            'id':mid,'actor':load_identity(self.user)['id'],
            'question':'What survives?','goal':'Recover committed state','share':True})
        self.stop(0)
        self.nodes[1].campaign()
        self.nodes[1].propose('workspace.contribute',{
            'id':mid,'actor':load_identity(self.user)['id'],
            'role':'verify','content':'Survives failure','expected_revision':1})
        self.assertEqual(self.nodes[2].view()['workspaces'][mid]['contributions'][0]['content'],
                         'Survives failure')
        self.start(0)
        self.nodes[1].heartbeat()
        self.assertEqual(self.nodes[0].view(),self.nodes[1].view())
        self.assertEqual(self.nodes[0].view(),self.nodes[2].view())

    def test_minority_partition_cannot_commit(self):
        self.nodes[0].campaign()
        self.stop(1);self.stop(2)
        with self.assertRaises(QuorumError):
            self.nodes[0].propose('workspace.open',{
                'id':'uncommitted','actor':self.nodes[0].node_id,
                'question':'A proposal without a majority',
                'goal':'Fail safely','share':True})
        self.assertEqual(self.nodes[0].view()['workspaces'],{})
        self.start(2)
        # A newer election recovers the uncommitted prefix only after durable majority.
        self.nodes[0].campaign()
        self.assertIn('uncommitted',self.nodes[2].view()['workspaces'])
        self.assertEqual(self.nodes[0].view(),self.nodes[2].view())

    def test_tampering_fails_journal_audit(self):
        self.nodes[0].campaign()
        self.nodes[0].propose('workspace.open',{
            'id':'audit','actor':self.nodes[0].node_id,
            'question':'Audit validity','goal':'Find corrupted entries','share':True})
        self.assertTrue(self.nodes[1].audit()['valid'])
        with self.nodes[1].tx() as db:
            db.execute('UPDATE log SET payload=? WHERE idx=1',('"tampered"',))
        result=self.nodes[1].audit()
        self.assertFalse(result['valid'])
        self.assertIn('Tampered',result['reason'])

    def test_no_individual_can_monopolize_active_workspaces(self):
        self.nodes[0].campaign()
        self.approved()
        who=load_identity(self.user)['id']
        for i in range(2):
            self.nodes[0].propose('workspace.open',{
                'id':f'limit-{i}','actor':who,
                'question':'Account fairness test','goal':'Equal access','share':True})
        with self.assertRaises(ValueError):
            self.nodes[0].propose('workspace.open',{
                'id':'third','actor':who,
                'question':'Account fairness test','goal':'Equal access','share':True})

    def test_reject_unknown_replica_and_external_ai(self):
        self.nodes[0].campaign()
        with self.assertRaises(RuntimeError):
            remote_state(f'http://127.0.0.1:{self.ports[0]}',self.user)
        forged= signed(load_identity(self.user),'q.vote',
                       {'term':80,'last_term':0,'last_index':0})
        with self.assertRaises(RuntimeError):
            post(f'http://127.0.0.1:{self.ports[0]}','/v2/quorum/vote',forged)
        self.assertEqual(self.nodes[0].status()['term'],1)

    def test_follower_cannot_become_leader_while_current_majority_holds(self):
        self.nodes[0].campaign()
        self.nodes[0].propose('workspace.open',{
            'id':'keep','actor':self.nodes[0].node_id,
            'question':'Existing committed data', 'goal':'Do not fork','share':True})
        # Campaign by another member is allowed, but only after gaining a new-term majority.
        self.nodes[1].campaign()
        self.assertEqual(self.nodes[1].status()['leader'],self.nodes[1].node_id)
        with self.assertRaises(QuorumError):
            self.nodes[0].propose('workspace.open',{
                'id':'stale','actor':self.nodes[0].node_id,
                'question':'Stale writes','goal':'Reject this','share':True})
        self.nodes[1].heartbeat()
        self.assertEqual(self.nodes[0].view(),self.nodes[1].view())


if __name__=='__main__':unittest.main()
