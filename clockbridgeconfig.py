"""
AUTHOR:     Beck D.
DATE:       2023-
PURPOSE:    This module handles loading and validating the configuration file for Clockbridge
"""

import os
import yaml
from typing_extensions import TypedDict, Literal
from pydantic import BaseModel, ValidationError, AnyHttpUrl, Base64Bytes, ValidationInfo, field_validator

class ConfigCredsSchema(TypedDict):
    """Config credentials schema for pushing into Elastic"""
    url: AnyHttpUrl
    insecure: bool
    username: str
    password: Base64Bytes
    index_prefix: str
    @field_validator('index_prefix')
    @classmethod
    def check_alphanumeric(cls, v: str, info: ValidationInfo) -> str:
        if isinstance(v, str):
            is_alphanumeric = v.replace(' ', '').isalnum()
            assert is_alphanumeric, f'{info.field_name} must be alphanumeric'
        return v

class ConfigSchema(BaseModel):
    """Schema for overall configuration file"""
    webhook_secrets: ( str | list[str] )
    event_types: ( str | list[str] )
    elastic_creds: ConfigCredsSchema
    log_level: Literal["DEBUG", "INFO", "WARN", "ERROR"] = "NOTSET"

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
                elif key == "event_types":
                    # Set all event_types to lowercase for comparisons
                    temp_list = [x.casefold() for x in value]
                    value = temp_list
                setattr(self, key, value)
            return True
        except ValidationError as e:
            raise ValueError("Config file is not in the expected schema") from e

    def __validate_args_length(self, args: list, expected_length: int):
        if isinstance(args, str):
            args = [ args ]
        return (all(len(arg) == expected_length for arg in args))
