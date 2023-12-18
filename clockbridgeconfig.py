import json
import os
import yaml
from typing_extensions import TypedDict
from pydantic import BaseModel, FilePath, ValidationError

class ConfigCredsSchema(TypedDict):
    location: FilePath

class ConfigSchema(BaseModel):
    webhook_secrets: (str | list[str])
    event_types: (str | list[str])
    sheets_creds: ConfigCredsSchema
    sheets_map: list[dict[str, str]]

class SheetsCredsSchema(BaseModel):
    type: str
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    auth_uri: str
    token_uri: str
    auth_provider_x509_cert_url: str
    client_x509_cert_url: str

class Config():
    def __init__(self, file_path):
        self.config_file = file_path
        self.webhook_secrets_len = 32
        self.sheets_id_len = 44
        self.file = self.__load_config_file(self.config_file)

    def __load_config_file(self, config_file_path):
        if os.access(config_file_path, os.R_OK):
            with open(config_file_path, "r", encoding="utf-8") as f:
                if f.readable():
                    verified_config = self.__parse_config_file(f)
                    return verified_config
                else:
                    raise IOError(f"{config_file_path} cannot be opened for reading")
        else:
            raise PermissionError(f"{config_file_path} cannot be opened for reading")

    def __parse_config_file(self, config_file):


        try:
            config = yaml.safe_load(config_file)
            schema = ConfigSchema
            validated_config = schema.model_validate(config)

            for key, value in dict(validated_config).items():
                if key == "webhook_secrets":
                    if not self.__validate_args_length(value, self.webhook_secrets_len):
                        raise ValueError(f"A value in {key} does not meet the expected length of {self.webhook_secrets_len}")
                elif key == "sheets_map":
                    if not all(self.__validate_args_length(item.values(), self.sheets_id_len) for item in value):
                        raise ValueError(f"A value in {key} does not meet the expected length of {self.sheets_id_len}")
                setattr(self, key, value)
            return True
        except ValidationError as e:
            raise ValueError("Config file is not in the expected schema") from e

    def __validate_args_length(self, args: list, expected_length: int):
        if isinstance(args, str):
            args = [ args ]
        if all(len(arg) == expected_length for arg in args):
            return True
        else:
            return False

    def load_sheets_creds(self, sheets_creds_path):
        if os.access(sheets_creds_path, os.R_OK):
            with open(sheets_creds_path, "r", encoding="utf-8") as f:
                if f.readable():
                    verified_creds = self.__validate_sheets_creds(f)
                    return verified_creds
                else:
                    raise IOError(f"{sheets_creds_path} cannot be opened for reading")
        else:
            raise PermissionError(f"{sheets_creds_path} cannot be opened for reading")

    def __validate_sheets_creds(self, sheets_creds):
        try:
            creds = json.load(sheets_creds)
            schema = SheetsCredsSchema
            validated_creds = schema.model_validate(creds)
            return dict(validated_creds)
        except ValidationError as e:
            raise ValueError("Config file is not in the expected schema") from e
