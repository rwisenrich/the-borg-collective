import unittest
from borg.mission import run_mission


class AwayMissionTests(unittest.TestCase):
    def test_three_offline_roles_plus_synthesis(self):
        packet={'mission_id':'m-1','brief':'Investigate alternative memory protocols',
                'collective_id':'borg-test','parent_hash':'abc123'}
        report=run_mission(packet,backend='mock')
        self.assertEqual(set(report['crew_results']),{'explore','challenge','verify'})
        self.assertIn('not an AI answer',report['report'])
        self.assertTrue(report['disconnected_research'])
        self.assertTrue(report['review_required'])
        self.assertEqual(report['collective_id'],packet['collective_id'])

    def test_invalid_mission_rejected(self):
        with self.assertRaises(ValueError):run_mission({'brief':''})
