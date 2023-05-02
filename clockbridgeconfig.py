import yaml
import json
import os
import schema

class Config():
    def load_config_file(self, config_file_path):
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
        config_schema = schema.Schema(
            {'config': 
                {
                    'webhook-secrets': [ str ],
                    'sheets-map': [ dict ],
                    'sheets-creds': {
                            'location': str
                    }
                }})

        try:
            config = yaml.safe_load(config_file)
            validated_config = config_schema.validate(config)
            return validated_config
        except (schema.SchemaError, schema.SchemaMissingKeyError):
            raise yaml.YAMLError(f"{config_file} is not in the expected schema")
        
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

if __name__ == "__main__":
    # For testing
    config = Config()
    config.load_config_file('config.yaml')