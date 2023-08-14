import sys
import os
import json
from io import StringIO
import yaml
import pytest
from clockbridgeconfig import Config
sys.path.append(os.path.abspath('../'))

config_path = os.environ.get('CLOCKBRIDGE_CONFIG_PATH')
if not config_path:
    raise ValueError('CONFIG_FILE_PATH environment variable is not set - please set the location of the configuration file')

class TestVerifyWebhookSignature:
    """ Test methods related to verifying the webhook signature """
    def setup_class(self):
        self.config = Config(config_path)

    def test_no_signature(self):
        """ Test for nonexistent signature """
        pass

    def test_signature_too_short(self):
        """ Test for signature being too short """
        pass

    def test_signature_too_long(self):
        """ Test for signature being too long """
        pass

    def test_signature_not_alphanumeric(self):
        """ Test for signature not being alphanumeric """
        pass

    def test_required_headers_present(self):
        """ Test whether all required headers are present """
        pass
