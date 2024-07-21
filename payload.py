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

class Payload:
    """Payload class"""
    def __init__(self, data):
        try:
            self.data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise json.JSONDecodeError("Unable to parse payload") from exc

    def validate_schema(self):
        """Validate the schema of the payload and ensure the duration matches start and end times"""
        try:
            schema = PayloadSchema
            self.data = schema.model_validate(self.data)
            delta = self.data.timeInterval['end'] - self.data.timeInterval['start']
            if delta != self.data.timeInterval['duration']:
                raise ValidationError
            self.data.timeInterval['start'] = self.data.timeInterval['start'].strftime('%Y-%m-%dT%H:%M:%S%z')
            self.data.timeInterval['end'] = self.data.timeInterval['end'].strftime('%Y-%m-%dT%H:%M:%S%z')
            self.data.timeInterval['duration'] = int(self.data.timeInterval['duration'].total_seconds())
            return True
        except ValidationError as exc:
            raise ValueError("Payload is not in the expected schema") from exc
