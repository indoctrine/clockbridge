import unittest
import yaml
import os
import json
from io import StringIO
from clockbridgeconfig import Config

class TestLoadConfigFile(unittest.TestCase):
    def setUp(self):
        self.config = Config()

    def test_invalid_path(self):
        """ Test for nonexistent/unreadable file """
        with self.assertRaises(IOError) as exception_context:
            self.config.load_config_file('nonexistent.yaml')
        
    def test_nonfile_path(self):
        """ Test for file being a directory """
        with self.assertRaises(IsADirectoryError) as exception_context:
            self.config.load_config_file(os.getcwd())

class TestParseConfigFile(unittest.TestCase):
    def setUp(self):
        self.config = Config()
    
    def test_invalid_config_file(self):
        """Test whether a valid non-YAML file is YAML"""
        invalid_config_file = StringIO("Not a real YAML file")
        with self.assertRaises(yaml.YAMLError) as exception_context:
            self.config._Config__parse_config_file(invalid_config_file)
    
    def test_invalid_config_schema(self):
        invalid_config_file = StringIO("""
config: 
    webhook-secrets: xxx
    sheets-creds: 
        location: config.yaml
        """)
        with self.assertRaises(yaml.YAMLError) as exception_context:
            self.config._Config__parse_config_file(invalid_config_file)

    def test_valid_config_file(self):
        valid_config_file = StringIO("""
config: 
    webhook-secrets: 
    - xxxxx
    - xxxxx
    sheets-map:
    - testing: test
    sheets-creds: 
        location: config.yaml
        """)
        self.assertIsInstance(self.config._Config__parse_config_file(valid_config_file), dict)

class TestLoadSheetsCreds(unittest.TestCase):
    def setUp(self):
        self.config = Config()

    def test_invalid_creds_file(self):
        """ Test for nonexistent/unreadable file """
        with self.assertRaises(IOError) as exception_context:
            self.config.load_sheets_creds('nonexistent.json')
        
    def test_creds_nonfile(self):
        """ Test for file being a directory """
        with self.assertRaises(IsADirectoryError) as exception_context:
            self.config.load_sheets_creds(os.getcwd())

class TestValidateSheetsCreds(unittest.TestCase):
    def setUp(self):
        self.config = Config()
    
    def test_invalid_creds_file(self):
        """Test whether a valid non-JSON file is JSON"""
        invalid_creds_file = StringIO("Not a real JSON file")
        with self.assertRaises(json.decoder.JSONDecodeError) as exception_context:
            self.config._Config__validate_sheets_creds(invalid_creds_file)
    
    def test_invalid_creds_schema(self):
        invalid_creds_file = StringIO("""
        {
                "type": "xxxx",
                "project_id": 123,
                "testing": "test",
            }""")
        with self.assertRaises(json.decoder.JSONDecodeError) as exception_context:
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
        self.assertIsInstance(self.config._Config__validate_sheets_creds(valid_creds_file), dict)

if __name__ == '__main__':
    import xmlrunner
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='test-config-report'))