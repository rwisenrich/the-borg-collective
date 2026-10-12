import unittest
from borg.volunteer import limits,donate

class OptIn(unittest.TestCase):
    def test_session_limits(self):
        self.assertEqual(limits(1,20,3)['max_jobs'],3)
        for t,m,j in ((0,10,1),(1,0,1),(1,2,0)):
            with self.assertRaises(ValueError):limits(t,m,j)

    def test_declines_without_consent_even_with_credentials(self):
        with self.assertRaises(PermissionError):
            donate('http://127.0.0.1:12345','unavailable.key','token',consent=False)

    def test_mock_donation_disallowed(self):
        with self.assertRaises(ValueError):
            donate('http://127.0.0.1:12345','unavailable.key','token',backend='mock',consent=True)

if __name__=='__main__':unittest.main()
