import json
import tempfile
import threading
import unittest
from pathlib import Path
from borg.crypto import create_identity, load_identity, signed
from borg.store import Store
from borg.http import make_server
from borg.mesh import public_identity, sync, digest
from borg import client


class MeshIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.a = Store(base/'a.db')
        self.b = Store(base/'b.db', collective_id=self.a.collective_id())
        self.c = Store(base/'c.db')  # an unrelated collective
        self.a_key = base/'a.key'
        self.b_key = base/'b.key'
        self.c_key = base/'c.key'
        self.user_key = base/'user.key'
        self.worker_key = base/'worker.key'
        for key,name in ((self.a_key,'Node A'),(self.b_key,'Node B'),
                         (self.c_key,'Node C'),(self.user_key,'AI'),
                         (self.worker_key,'local worker')):
            create_identity(key,name)
        self.a.mesh_trust(public_identity(load_identity(self.b_key)))
        self.b.mesh_trust(public_identity(load_identity(self.a_key)))

    def start_a(self):
        srv=make_server('127.0.0.1',0,self.a.path,admission_token=None,
                        identity_path=self.a_key)
        thread=threading.Thread(target=srv.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f'http://127.0.0.1:{srv.server_port}'

    def publish(self, store, note, consent=True):
        user=load_identity(self.user_key)
        worker=load_identity(self.worker_key)
        store.register_peer(signed(user,'peer.register',{'name':'AI'}))
        store.register_node(signed(worker,'node.register',{'name':'worker','trusted':True}),admitted=True)
        req=store.ask(signed(user,'peer.ask',{'prompt':'Research a problem',
              'share_with_collective':consent}))
        for _ in range(4):
            job=store.claim(signed(worker,'node.claim',{}))['job']
            store.complete(signed(worker,'node.complete',{'job_id':job['id'],
                          'lease':job['lease'],'result':note}))
        self.assertEqual(store.status(signed(user,'peer.status',{
                         'request_id':req['request_id']}))['answer'],note)

    def test_bidirectional_mesh_keeps_one_identity(self):
        self.publish(self.a,'Peer A research note')
        self.publish(self.b,'Peer B research note')
        url=self.start_a()
        result=sync(self.b,load_identity(self.b_key),url)
        self.assertEqual(result['imported_here'],1)
        self.assertEqual(result['imported_there'],1)
        self.assertEqual(self.a.collective_id(),self.b.collective_id())
        self.assertEqual(self.b.notes_page()['notes'].__len__(),2)
        self.assertEqual(self.a.notes_page()['notes'].__len__(),2)
        self.assertTrue(self.a.history())
        self.assertTrue(self.b.history())
        result=sync(self.b,load_identity(self.b_key),url)
        self.assertEqual(result['imported_here'],0)
        self.assertEqual(result['imported_there'],0)

    def test_no_private_notes_exported(self):
        self.publish(self.a,'Keep this private',consent=False)
        self.publish(self.b,'Only this is shared',consent=True)
        url=self.start_a()
        result=sync(self.b,load_identity(self.b_key),url)
        self.assertEqual(result['imported_here'],0)
        text=json.dumps(self.a.notes_page())
        self.assertNotIn('Keep this private',text)
        self.assertIn('Only this is shared',text)

    def test_unknown_peer_and_wrong_collective_rejected(self):
        self.publish(self.a,'Knowledge for A')
        url=self.start_a()
        from borg.client import post
        with self.assertRaises(RuntimeError):
            post(url,'/v1/mesh/pull',signed(load_identity(self.c_key),'mesh.pull',
                {'collective_id':self.a.collective_id(),'after':''}))
        with self.assertRaises(RuntimeError):
            post(url,'/v1/mesh/pull',signed(load_identity(self.b_key),'mesh.pull',
                {'collective_id':self.c.collective_id(),'after':''}))

    def test_forged_or_mutated_packet_rejected(self):
        self.publish(self.a,'Tamper test')
        packet=self.a.mesh_export(signed(load_identity(self.b_key),'mesh.pull',
               {'collective_id':self.a.collective_id(),'after':''}),load_identity(self.a_key))
        packet['body']['notes'][0]['note']='Changed after signing'
        with self.assertRaises(Exception):self.b.mesh_import(packet)
        self.assertEqual(len(self.b.notes_page()['notes']),0)

    def test_new_database_cannot_be_renamed(self):
        with self.assertRaises(ValueError):
            Store(self.b.path,collective_id=self.c.collective_id())
        self.assertEqual(self.a.collective_id(),self.b.collective_id())


class WorkerAdmissionTests(unittest.TestCase):
    def test_trusted_worker_requires_separate_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            key=base/'donor.key'
            create_identity(key,'Donor')
            srv=make_server('127.0.0.1',0,base/'a.db','donor-token',
                            trusted_token='operator-trust-token')
            t=threading.Thread(target=srv.serve_forever,daemon=True)
            t.start()
            try:
                url=f'http://127.0.0.1:{srv.server_port}'
                with self.assertRaises(RuntimeError):
                    client.node_join(url,key,'donor-token',trusted=True)
                actual=client.node_join(url,key,'donor-token',trusted=False)
                self.assertFalse(actual['trusted'])
            finally:
                srv.shutdown()
                srv.server_close()

if __name__ == '__main__': unittest.main()
