import copy
import tempfile
import unittest
from pathlib import Path
from borg.crypto import create_identity,load_identity
from borg.mesh import public_identity
from borg.away import create,contribute,merge,validate,return_payload
from borg.quorum import QuorumError
from tests.test_quorum import Cluster


class DetachedCrew(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        root=Path(self.t.name)
        self.keys=[root/f'crew{x}.key' for x in range(2)]
        self.uninvited=root/'other.key'
        for i,p in enumerate(self.keys):create_identity(p,f'Crew member {i}')
        create_identity(self.uninvited,'Unknown visitor')
        self.crew=[public_identity(load_identity(p)) for p in self.keys]
        self.root=create('collective-test','mission-1',7,'Compute a research hypothesis',self.crew)

    def test_offline_two_members_merge_and_verify(self):
        a=contribute(self.root,self.keys[0],'explore','A mathematical candidate.')
        b=contribute(self.root,self.keys[1],'verify','A check of the candidate.')
        both=merge(a,b)
        self.assertEqual(validate(both)['entries'],2)
        self.assertEqual(len(merge(both,a)['entries']),2)
        self.assertEqual(return_payload(both,'A combined, reviewed result.')['crew_digest'],validate(both)['digest'])

    def test_unknown_identity_or_mutated_payload_rejected(self):
        with self.assertRaises(PermissionError):
            contribute(self.root,self.uninvited,'explore','Unauthorized report')
        a=contribute(self.root,self.keys[0],'explore','Original result')
        fake=copy.deepcopy(a)
        fake['entries'][0]['body']['content']='Modified after signing'
        with self.assertRaises(PermissionError):validate(fake)
        with self.assertRaises(ValueError):merge(a,create('other','mission-1',7,'Compute a research hypothesis',self.crew))


class DetachedMissionReunion(Cluster):
    def test_signed_away_rejoins_after_parent_failover(self):
        self.nodes[0].campaign()
        self.approved()
        from borg.crypto import signed
        import uuid
        base=self.nodes[0].view()['commit']
        parent_actor=load_identity(self.user)['id']
        mission_id='mission-'+uuid.uuid4().hex
        self.nodes[0].propose('mission.detach',{
            'id':mission_id,'brief':'Offline independent check','base':base,
            'members':[parent_actor]})
        crew=[public_identity(load_identity(self.user))]
        detached=create(self.nodes[0].config['collective_id'],mission_id,base,'Offline independent check',crew)
        detached=contribute(detached,self.user,'verify','Independent signed offline evidence')
        self.stop(0)
        self.nodes[1].campaign()
        payload=return_payload(detached,'Reconciled signed mission summary')
        payload['actor']=parent_actor
        self.nodes[1].propose('mission.return',payload)
        found=self.nodes[2].view()['missions'][mission_id]
        self.assertEqual(found['status'],'returned-unreviewed')
        self.assertEqual(len(found['reports']),1)
        bad=copy.deepcopy(payload)
        bad['content']='Claim without valid bundle'
        bad['crew_bundle']['entries'][0]['body']['content']='Forged work'
        with self.assertRaises(PermissionError):
            self.nodes[1].propose('mission.return',bad)
