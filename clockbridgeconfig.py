import yaml
import json
import os
import schema
from schema import Use, And, Or

class Config():
    def __init__(self, file_path):
        self.config_file = file_path
        self.file = self.__load_config_file(self.config_file)

    def __load_config_file(self, config_file_path):
        if os.access(config_file_path, os.R_OK):
            with open(config_file_path, "r") as f:
                if f.readable():
                    verified_config = self.__parse_config_file(f)
                    return verified_config
                else:
                    raise IOError(f"{config_file_path} cannot be opened for reading")
        else:
            raise PermissionError(f"{config_file_path} cannot be opened for reading")

    def __parse_config_file(self, config_file):
        self.webhook_secrets_len = 32
        self.sheets_id_len = 44
        config_schema = schema.Schema(
            {'config': 
                {
                    'webhook_secrets': [ str ], 
                    'sheets_map': [ dict ],
                    'event_types': Or(And([ str ], Use(lambda s: [ x.lower() for x in s ])), And(str, Use(str.lower))),
                    'sheets_creds': {
                            'location': str
                    }
                }
            }
        )
        
        try:
            config = yaml.safe_load(config_file)
            validated_config = config_schema.validate(config)
            for key, value in validated_config['config'].items():
                if key == "webhook_secrets":
                    if self.__validate_args_length(value, self.webhook_secrets_len) in value:
                        raise schema.SchemaError(f"A value in {key} does not meet the expected length of {self.webhook_secrets_len}")
                elif key == "sheets_map":
                    if not all(self.__validate_args_length(item.values(), self.sheets_id_len) for item in value):
                        raise schema.SchemaError(f"A value in {key} does not meet the expected length of {self.sheets_id_len}")
                setattr(self, key, value)
            return True
        except (schema.SchemaError, schema.SchemaMissingKeyError):
            raise yaml.YAMLError(f"{config_file} is not in the expected schema")
    
    def __validate_args_length(self, args, expected_length):
        if all(len(arg) == expected_length for arg in args):
            return True
        else:
            return False

    def load_sheets_creds(self, sheets_creds_path):
        if os.access(sheets_creds_path, os.R_OK):
            with open(sheets_creds_path, "r") as f:
                if f.readable():
                    verified_creds = self.__validate_sheets_creds(f)
                    return verified_creds
                else:
                    raise IOError(f"{sheets_creds_path} cannot be opened for reading")
        else:
            raise PermissionError(f"{sheets_creds_path} cannot be opened for reading")
        
    def __validate_sheets_creds(self, sheets_creds):
        creds_schema = schema.Schema(
            {
                "type": str,
                "project_id": str,
                "private_key_id": str,
                "private_key": str,
                "client_email": str,
                "client_id": str,
                "auth_uri": str,
                "token_uri": str,
                "auth_provider_x509_cert_url": str,
                "client_x509_cert_url": str
            }
        )

        try:
            creds = json.load(sheets_creds)
            validated_creds = creds_schema.validate(creds)
            return validated_creds
        except (schema.SchemaError, schema.SchemaMissingKeyError):
            raise json.decoder.JSONDecodeError(f"{sheets_creds} is not in the expected schema")