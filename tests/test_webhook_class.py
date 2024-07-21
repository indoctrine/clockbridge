import sys
import os
import json
from clockbridgeconfig import Config
from webhook import Webhook
import pytest
sys.path.append(os.path.abspath('../'))

config_path = os.path.join(os.getcwd(), "tests/testConfig.yaml")

class TestVerifyWebhookSignature:
    """ Test methods related to verifying the webhook signature """
    def setup_class(self):
        self.config = Config(config_path)
        self.hook = Webhook(self.config)

    def test_no_signature(self):
        """ Test for nonexistent signature """
        headers = {}
        assert self.hook.verify_signature(headers) is False

    def test_signature_empty(self):
        """ Test for signature being empty """
        headers = {"Clockify-Signature": "", "Clockify-Webhook-Event-Type": "NEW_TIME_ENTRY"}
        assert self.hook.verify_signature(headers) is False

    def test_signature_too_short(self):
        """ Test for signature being too short """
        headers = {"Clockify-Signature": "signaturelessthan32chars", "Clockify-Webhook-Event-Type": "NEW_TIME_ENTRY"}
        assert self.hook.verify_signature(headers) is False

    def test_signature_too_long(self):
        """ Test for signature being too long """
        headers = {"Clockify-Signature": "thissignatureisgreaterthan32chars", "Clockify-Webhook-Event-Type": "NEW_TIME_ENTRY"}
        assert self.hook.verify_signature(headers) is False

    def test_signature_is_correct(self):
        """ Test for a correct signature """
        headers = {"Clockify-Signature": self.config.webhook_secrets[0], "Clockify-Webhook-Event-Type": "NEW_TIME_ENTRY"}
        assert self.hook.verify_signature(headers) is True

    def test_non_dict_headers(self):
        """ Test whether using something other than a dictionary handles gracefully """
        headers = []
        assert self.hook.verify_signature(headers) is False

class TestVerifyWebhookPayload:
    """ Test methods related to verifying the webhook payload """
    def setup_class(self):
        self.config = Config(config_path)
        self.hook = Webhook(self.config)
        json_data = """
        {
            "description": "",
            "id": "",
            "project": {
                "clientId": "",
                "clientName": "",
                "estimate": {
                    "estimate": "PT0S",
                    "type": "AUTO"
                },
                "name": "",
                "workspaceId": ""
            },
            "projectId": "",
            "timeInterval": {
                "duration": "",
                "end": "",
                "start": ""
            },
            "userId": ""
        }
        """
        self.payload = json.loads(json_data)

    def test_no_payload(self):
        """ Test for nonexistent signature """
        payload = {}
        with pytest.raises(ValueError):
            self.hook.verify_payload(payload)

    def test_required_fields_null(self):
        """ Test for required fields being null"""
        with pytest.raises(ValueError):
            self.hook.verify_payload(self.payload)

    def test_start_time_before_end_time(self):
        """ Test that the start_time is before the end_time """
        payload = self.payload
        payload["timeInterval"]["start"] = "2023-03-28T09:05:13Z"
        payload["timeInterval"]["end"] = "2023-03-29T09:05:13Z"
        with pytest.raises(ValueError):
            self.hook.verify_payload(self.payload)
