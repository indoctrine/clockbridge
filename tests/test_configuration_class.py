import sys
import os
import json
from io import StringIO
import yaml
import pytest
from clockbridgeconfig import Config
import schema
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
        self.sheets_id_len = 44

    def test_invalid_config_file(self):
        """Test whether a valid non-YAML file is YAML"""
        invalid_config_file = StringIO("Not a real YAML file")
        with pytest.raises(yaml.YAMLError):
            self.config._Config__parse_config_file(invalid_config_file)

    def test_invalid_config_schema(self):
        """Test a valid YAML file in incorrect schema"""
        invalid_config_file = StringIO("""
config: 
    webhook_secrets: xxx
    sheets_creds: 
        location: testSecrets.json
        """)
        with pytest.raises(yaml.YAMLError):
            self.config._Config__parse_config_file(invalid_config_file)

    def test_valid_config_file(self):
        """Test a valid YAML file in the correct schema returns the expected data structures"""

        assert isinstance(self.config.webhook_secrets, list)
        assert all(len(val) == self.webhook_secrets_len for val in self.config.webhook_secrets)
        assert isinstance(self.config.sheets_map, list)    
        assert all(isinstance(item, dict) for item in self.config.sheets_map)
        assert all(all(len(val) == self.sheets_id_len for val in d.values()) for d in self.config.sheets_map)
        assert isinstance(self.config.event_types, list) or isinstance(self.config.event_types, str)
        assert isinstance(self.config.sheets_creds, dict)

class TestLoadSheetsCreds:
    """ Test methods related to loading the Google Sheets credentials file """
    def setup_class(self):
        self.config = Config(config_path)

    def test_invalid_creds_file(self):
        """ Test for nonexistent/unreadable file """
        with pytest.raises(IOError):
            self.config.load_sheets_creds('nonexistent.json')

    def test_creds_nonfile(self):
        """ Test for file being a directory """
        with pytest.raises(IsADirectoryError):
            self.config.load_sheets_creds(os.getcwd())

class TestValidateSheetsCreds:
    """ Test methods related to validating the Google Sheets credentials file """
    def setup_class(self):
        self.config = Config(config_path)

    def test_invalid_creds_file(self):
        """Test whether a valid non-JSON file is JSON"""
        invalid_creds_file = StringIO("Not a real JSON file")
        with pytest.raises(json.decoder.JSONDecodeError):
            self.config._Config__validate_sheets_creds(invalid_creds_file)

    def test_invalid_creds_schema(self):
        """Test a valid JSON file in incorrect schema"""
        invalid_creds_file = StringIO("""
        {
                "type": "xxxx",
                "project_id": 123,
                "testing": "test",
            }""")
        with pytest.raises(json.decoder.JSONDecodeError):
            self.config._Config__validate_sheets_creds(invalid_creds_file)

    def test_valid_creds_file(self):
        """Test a valid JSON file in the correct schema returns the expected data structures"""
        valid_creds_file = StringIO("""
            {
                "type": "test",
                "project_id": "12345",
                "private_key_id": "xxxx",
                "private_key": "yyyy",
                "client_email": "foo@bar.com",
                "client_id": "zzzz",
                "auth_uri": "https://example.com/auth",
                "token_uri": "https://example.com/auth/token",
                "auth_provider_x509_cert_url": "https://example.com/auth/x509",
                "client_x509_cert_url": "https://example.com/client/x509"
            }
        """)
        assert isinstance(self.config._Config__validate_sheets_creds(valid_creds_file), dict)
