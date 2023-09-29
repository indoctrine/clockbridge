import sys
import os
from io import StringIO
import pytest
from clockbridgeconfig import Config
from clockbridge import Clockbridge
sys.path.append(os.path.abspath('../'))

config_path = os.environ.get('CLOCKBRIDGE_CONFIG_PATH')
if not config_path:
    raise ValueError('CONFIG_FILE_PATH environment variable is not set - please set the location of the configuration file')

class TestVerifyWebhookSignature:
    """ Test methods related to verifying the webhook signature """
    def setup_class(self):
        self.config = Config(config_path)
        self.bridge = Clockbridge()

    def test_no_signature(self):
        """ Test for nonexistent signature """
        headers = {}
        assert self.bridge.verify_webhook_signature(headers, self.config) is False

    def test_signature_empty(self):
        """ Test for signature being empty """
        headers = {"Clockify-Signature": "", "Clockify-Webhook-Event-Type": "NEW_TIME_ENTRY"}
        assert self.bridge.verify_webhook_signature(headers, self.config) is False

    def test_signature_too_short(self):
        """ Test for signature being too short """
        headers = {"Clockify-Signature": "signaturelessthan32chars", "Clockify-Webhook-Event-Type": "NEW_TIME_ENTRY"}
        assert self.bridge.verify_webhook_signature(headers, self.config) is False

    def test_signature_too_long(self):
        """ Test for signature being too long """
        headers = {"Clockify-Signature": "thissignatureisgreaterthan32chars", "Clockify-Webhook-Event-Type": "NEW_TIME_ENTRY"}
        assert self.bridge.verify_webhook_signature(headers, self.config) is False

    def test_signature_is_correct(self):
        """ Test for a correct signature """
        headers = {"Clockify-Signature": self.config.webhook_secrets[0], "Clockify-Webhook-Event-Type": "NEW_TIME_ENTRY"}
        assert self.bridge.verify_webhook_signature(headers, self.config) is True

    def test_non_dict_headers(self):
        """ Test whether using something other than a dictionary handles gracefully """
        headers = []
        assert self.bridge.verify_webhook_signature(headers, self.config) is False