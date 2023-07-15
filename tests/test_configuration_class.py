import sys
import os
import json
from io import StringIO
import yaml
import pytest
from clockbridgeconfig import Config
sys.path.append(os.path.abspath('../'))

class TestLoadConfigFile:
    def test_invalid_path(self):
        """ Test for nonexistent/unreadable file """
        with pytest.raises(IOError):
            self.config = Config('nonexistent.yaml')
        
    def test_nonfile_path(self):
        """ Test for file being a directory """
        with pytest.raises(IsADirectoryError):
            self.config = Config(os.getcwd())

class TestParseConfigFile:
    def setup_class(self):
        self.config = Config('config.yaml')
    
    def test_invalid_config_file(self):
        """Test whether a valid non-YAML file is YAML"""
        invalid_config_file = StringIO("Not a real YAML file")
        with pytest.raises(yaml.YAMLError):
            self.config._Config__parse_config_file(invalid_config_file)
    
    def test_invalid_config_schema(self):
        invalid_config_file = StringIO("""
config: 
    webhook_secrets: xxx
    sheets_creds: 
        location: config.yaml
        """)
        with pytest.raises(yaml.YAMLError):
            self.config._Config__parse_config_file(invalid_config_file)

    def test_valid_config_file(self):
        valid_config_file = StringIO("""
config: 
    webhook_secrets: 
    - xxxxx
    - xxxxx
    sheets_map:
    - testing: test
    sheets_creds: 
        location: config.yaml
        """)
        assert type(self.config._Config__parse_config_file(valid_config_file)) is bool 
        assert type(self.config.webhook_secrets) is list
        assert type(self.config.sheets_map) is list
        assert type(self.config.sheets_creds) is dict

class TestLoadSheetsCreds:
    def setup_class(self):
        self.config = Config('config.yaml')

    def test_invalid_creds_file(self):
        """ Test for nonexistent/unreadable file """
        with pytest.raises(IOError):
            self.config.load_sheets_creds('nonexistent.json')
        
    def test_creds_nonfile(self):
        """ Test for file being a directory """
        with pytest.raises(IsADirectoryError):
            self.config.load_sheets_creds(os.getcwd())

class TestValidateSheetsCreds:
    def setup_class(self):
        self.config = Config('config.yaml')

    def test_invalid_creds_file(self):
        """Test whether a valid non-JSON file is JSON"""
        invalid_creds_file = StringIO("Not a real JSON file")
        with pytest.raises(json.decoder.JSONDecodeError):
            self.config._Config__validate_sheets_creds(invalid_creds_file)
    
    def test_invalid_creds_schema(self):
        invalid_creds_file = StringIO("""
        {
                "type": "xxxx",
                "project_id": 123,
                "testing": "test",
            }""")
        with pytest.raises(json.decoder.JSONDecodeError):
            self.config._Config__validate_sheets_creds(invalid_creds_file)

    def test_valid_creds_file(self):
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
        assert type(self.config._Config__validate_sheets_creds(valid_creds_file)) is dict