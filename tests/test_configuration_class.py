import sys
import os
import json
from io import StringIO
import yaml
import pytest
from clockbridgeconfig import Config
sys.path.append(os.path.abspath('../'))

config_path = os.path.join(os.getcwd(), "tests/testConfig.yaml")

class TestLoadConfigFile:
    """ Test methods related to loading the configuration file """
    def test_invalid_path(self):
        """ Test for nonexistent/unreadable file """
        with pytest.raises(IOError):
            self.config = Config('nonexistent.yaml')

    def test_nonfile_path(self):
        """ Test for file being a directory """
        with pytest.raises(IsADirectoryError):
            self.config = Config(os.getcwd())

class TestParseConfigFile:
    """ Test methods related to parsing the configuration file """
    def setup_class(self):
        self.config = Config(config_path)
        self.webhook_secrets_len = 32

    def test_invalid_config_file(self):
        """Test whether a valid non-YAML file is YAML"""
        invalid_config_file = StringIO("Not a real YAML file")
        with pytest.raises(ValueError):
            self.config._Config__parse_config_file(invalid_config_file)

    def test_invalid_config_schema(self):
        """Test a valid YAML file in incorrect schema"""
        invalid_config_file = StringIO("""
config: 
    webhook_secrets: xxx
    sheets_creds: 
        location: abc
        """)
        with pytest.raises(ValueError):
            self.config._Config__parse_config_file(invalid_config_file)

    def test_valid_config_file(self):
        """Test a valid YAML file in the correct schema returns the expected data structures"""
        assert isinstance(self.config.webhook_secrets, list)
        assert all(len(val) == self.webhook_secrets_len for val in self.config.webhook_secrets)
        assert isinstance(self.config.event_types, list) or isinstance(self.config.event_types, str)
        assert isinstance(self.config.elastic_creds, dict)