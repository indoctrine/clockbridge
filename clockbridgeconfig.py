"""
AUTHOR:     Beck D.
DATE:       2023-
PURPOSE:    This module handles loading and validating the configuration file for Clockbridge
"""
import json
import os
import yaml
from typing_extensions import TypedDict
from pydantic import BaseModel, ValidationError, AnyHttpUrl, Base64Bytes

class ConfigCredsSchema(TypedDict):
    """Config credentials schema for pushing into Elastic"""
    url: AnyHttpUrl
    insecure: bool
    username: str
    password: Base64Bytes

class ConfigSchema(BaseModel):
    """Schema for overall configuration file"""
    webhook_secrets: ( str | list[str] )
    event_types: ( str | list[str] )
    elastic_creds: ConfigCredsSchema

class Config():
    """Singleton config class where the magic happens"""
    def __init__(self, file_path):
        self.config_file = file_path
        self.webhook_secrets_len = 32
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