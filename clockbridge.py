"""
AUTHOR:     Beck D.
DATE:       2023-
PURPOSE:    This module handles validating the incoming payload for Clockbridge
"""
import json
from typing import Optional
from datetime import datetime, timedelta
from typing_extensions import TypedDict
from pydantic import BaseModel, ValidationError

class PayloadProjectSchema(TypedDict):
    """Validate the Project dictionary in payload"""
    clientId: str
    clientName: str
    name: str

class PayloadTimeSchema(TypedDict):
    """Validate the TimeInterval dictionary in payload"""
    duration: timedelta
    end: datetime
    start: datetime

class PayloadSchema(BaseModel):
    """Validate the Payload schema"""
    description: str
    id: str
    project: Optional[PayloadProjectSchema]
    projectId: Optional[str]
    timeInterval: PayloadTimeSchema

class Clockbridge:
    """Overarching class where the magic happens"""
    def __init__(self, config):
        self.config = config

    def verify_incoming_webhook(self, headers, payload):
        """Verify signature and payload"""
        verify_payload = self.verify_webhook_payload(payload)
        if self.verify_webhook_signature(headers) and verify_payload:
            return verify_payload
        else:
            return False

    def verify_webhook_signature(self, request_headers):
        """Verify the webhook headers contain correct signature"""
        expected_keys = ['clockify-signature', 'clockify-webhook-event-type']
        headers = self.__normalise_headers(request_headers)
        if not headers:
            return False
        else:
            missing_headers = set(expected_keys).difference(headers.keys())
            if missing_headers:
                return False
        if (headers['clockify-signature'] in self.config.webhook_secrets and 
            headers['clockify-webhook-event-type'].casefold() in self.config.event_types):
            return True
        else:
            return False
        
    def __normalise_headers(self, request_headers):
        try:
            headers = dict(request_headers)
            for header_key, header in dict(request_headers).items():
                headers[header_key.casefold()] = header
                headers.pop(header_key)
            return headers
        except ValueError:
            return None
        
    def verify_webhook_payload(self, payload):
        try:
            parsed_payload = json.loads(payload)
        except:
            return False
        try:
            schema = PayloadSchema
            validated_payload = schema.model_validate(parsed_payload)
        except ValidationError as e:
            raise ValueError("Payload is not in the expected schema") from e
        return validated_payload
