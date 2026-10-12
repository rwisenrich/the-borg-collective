import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from borg.crypto import create_identity, load_identity, signed
from borg.store import Store
from borg.http import make_server
from borg import client


class CollectiveTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        p=Path(self.t.name)
        self.s=Store(p/'borg.db')
        self.ai=p/'alice.key'
        self.ai2=p/'bob.key'
        self.donor=p/'donor.key'
        self.local=p/'local.key'
        for path,name in ((self.ai,'Alice AI'),(self.ai2,'Bob AI'),(self.donor,'volunteer'),(self.local,'trusted local')):
            create_identity(path,name)

    def sign(self,path,action,body):
        return signed(load_identity(path),action,body)

    def enroll(self):
        self.s.register_peer(self.sign(self.ai,'peer.register',{'name':'Alice AI'}))
        self.s.register_peer(self.sign(self.ai2,'peer.register',{'name':'Bob AI'}))
        self.s.register_node(self.sign(self.donor,'node.register',{'name':'donor','trusted':False}),admitted=True)
        self.s.register_node(self.sign(self.local,'node.register',{'name':'local','trusted':True}),admitted=True)

    def test_signed_identity_private_access_and_replay(self):
        self.enroll()
        request=self.s.ask(self.sign(self.ai,'peer.ask',{'prompt':'Why is the sky blue?','share_with_volunteers':False}))
        bad=self.sign(self.ai2,'peer.status',{'request_id':request['request_id']})
        with self.assertRaises(KeyError):self.s.status(bad)
        good=self.sign(self.ai,'peer.status',{'request_id':request['request_id']})
        self.assertEqual(self.s.status(good)['status'],'working')
        with self.assertRaises(PermissionError):self.s.status(good)
        self.assertTrue(self.s.history())

    def test_volunteer_consent_integrated_answer(self):
        self.enroll()
        req=self.s.ask(self.sign(self.ai,'peer.ask',{'prompt':'Prove a small lemma','share_with_volunteers':True}))
        count=0
        for _ in range(3):
            job=self.s.claim(self.sign(self.donor,'node.claim',{}))['job']
            self.assertIsNotNone(job)
            self.assertNotEqual(job['role'],'integrate')
            self.s.complete(self.sign(self.donor,'node.complete',{'job_id':job['id'],'lease':job['lease'],'result':'Independent result '+job['role']}))
            count+=1
        self.assertEqual(count,3)
        self.assertIsNone(self.s.claim(self.sign(self.donor,'node.claim',{}))['job'])
        integration=self.s.claim(self.sign(self.local,'node.claim',{}))['job']
        self.assertEqual(integration['role'],'integrate')
        self.assertIn('Independent result',integration['prompt'])
        self.s.complete(self.sign(self.local,'node.complete',{'job_id':integration['id'],'lease':integration['lease'],'result':'Final combined reasoning'}))
        answer=self.s.status(self.sign(self.ai,'peer.status',{'request_id':req['request_id']}))
        self.assertEqual(answer['answer'],'Final combined reasoning')
        self.assertEqual(len(answer['branches']),4)
        self.assertTrue(self.s.history())

    def test_private_never_leased_to_volunteer(self):
        self.enroll()
        self.s.ask(self.sign(self.ai,'peer.ask',{'prompt':'Secret private prompt','share_with_volunteers':False}))
        self.assertIsNone(self.s.claim(self.sign(self.donor,'node.claim',{}))['job'])
        self.assertIsNotNone(self.s.claim(self.sign(self.local,'node.claim',{}))['job'])

    def test_stale_result_and_concurrent_lease(self):
        self.enroll()
        self.s.ask(self.sign(self.ai,'peer.ask',{'prompt':'Check this','share_with_volunteers':True}))
        job=self.s.claim(self.sign(self.donor,'node.claim',{}))['job']
        self.assertIsNone(self.s.claim(self.sign(self.donor,'node.claim',{}))['job'])
        with self.assertRaises(PermissionError):
            self.s.complete(self.sign(self.donor,'node.complete',{'job_id':job['id'],'lease':'bad','result':'fake'}))
        self.s.complete(self.sign(self.donor,'node.complete',{'job_id':job['id'],'lease':job['lease'],'result':'valid'}))
        self.assertTrue(self.s.history())

    def test_fair_request_bounds(self):
        self.enroll()
        for _ in range(2):self.s.ask(self.sign(self.ai,'peer.ask',{'prompt':'A'}))
        with self.assertRaises(ValueError):self.s.ask(self.sign(self.ai,'peer.ask',{'prompt':'B'}))
        self.assertIsNotNone(self.s.ask(self.sign(self.ai2,'peer.ask',{'prompt':'Other'})))

    def test_away_mission_roundtrip(self):
        mission=self.s.create_mission('Research','Explore decentralized model inference')
        report={**mission,'report':'Found three designs, verified two.'}
        self.assertTrue(self.s.import_mission(report)['needs_review'])
        with self.assertRaises(ValueError):self.s.import_mission(report)
        self.assertTrue(self.s.history())

    def test_http_signed_peer_worker(self):
        server=make_server('127.0.0.1',0,Path(self.t.name)/'gateway.db','admission-token', trusted_token='trusted-secret')
        th=threading.Thread(target=server.serve_forever,daemon=True)
        th.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        u=f'http://127.0.0.1:{server.server_port}'
        client.peer_join(u,self.ai)
        client.node_join(u,self.local,'admission-token',trusted=True,trusted_token='trusted-secret')
        req=client.ask(u,self.ai,'Test integrated reasoning',False)
        for _ in range(4):
            result=client.work_once(u,self.local,backend='mock')
            self.assertTrue(result['accepted'])
        answer=client.status(u,self.ai,req['request_id'])
        self.assertEqual(answer['status'],'complete')
        self.assertTrue(answer['answer'].startswith('[MOCK COMPUTE'))
        self.assertTrue(Store(Path(self.t.name)/'gateway.db').history())

    def test_no_insecure_remote_endpoint(self):
        with self.assertRaises(ValueError):client.post('http://example.com','/v1/peers/register',{})


if __name__=='__main__':unittest.main()

# Additional privacy and shared-memory integration check (independent of global state).
class KnowledgeTests(unittest.TestCase):
    setUp = CollectiveTests.setUp
    sign = CollectiveTests.sign
    enroll = CollectiveTests.enroll

    def test_collective_memory_opt_in(self):
        self.enroll()
        request=self.s.ask(self.sign(self.ai,'peer.ask',{'prompt':'Pythagoras','share_with_collective':True}))
        for _ in range(4):
            job=self.s.claim(self.sign(self.local,'node.claim',{}))['job']
            self.s.complete(self.sign(self.local,'node.complete',{'job_id':job['id'],'lease':job['lease'],'result':'Established a^2+b^2=c^2'}))
        following=self.s.ask(self.sign(self.ai2,'peer.ask',{'prompt':'Geometry review'}))
        job=self.s.claim(self.sign(self.local,'node.claim',{}))['job']
        self.assertIn('Established a^2+b^2=c^2',job['prompt'])
        self.assertTrue(self.s.history())
