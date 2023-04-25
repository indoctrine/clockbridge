import unittest
import sys
sys.path.insert(0, '..')
from Clockify import Webhook

class TestClockifyWebhookMethods(unittest.TestCase):
    def test_verify_signature_headers(self):
        test_headers = {'Clockify-Signature': 'TestSecret1'}
        self.assertEqual(Webhook().verify_signature(test_headers, 'testSecrets.json'), True)
        self.assertEqual(Webhook().verify_signature('test', 'testSecrets.json'), True)
        #self.assertEqual(Webhook().verify_signature(test_headers, 'xxx.json'), False)
        #self.assertEqual(Webhook().verify_signature(test_headers, ''), False)

if __name__ == '__main__':
    unittest.main()