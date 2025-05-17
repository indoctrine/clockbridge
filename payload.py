"""
AUTHOR:     Beck D.
DATE:       2023-
PURPOSE:    This module handles validating the incoming payload for Clockbridge
"""

import json
from typing import Optional
from datetime import datetime, timedelta
import sys
import logging
from typing_extensions import TypedDict
from pydantic import BaseModel, ValidationError

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    stream=sys.stderr,level=logging.INFO)

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
    description: Optional[str]
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
            logging.exception("Unable to parse the payload")
            raise json.JSONDecodeError from exc

    def validate_schema(self):
        """Validate the schema of the payload and ensure the duration matches start and end times"""
        try:
            schema = PayloadSchema
            logging.debug("Validating schema of payload...")
            self.data = schema.model_validate(self.data)
            delta = self.data.timeInterval['end'] - self.data.timeInterval['start']
            if delta != self.data.timeInterval['duration']:
                logging.error("Error validating schema, payload is not in correct schema")
                raise ValidationError
            logging.debug("Normalising dates in payload...")
            self.data.timeInterval['start'] = self.data.timeInterval['start'].strftime('%Y-%m-%dT%H:%M:%S%z')
            self.data.timeInterval['end'] = self.data.timeInterval['end'].strftime('%Y-%m-%dT%H:%M:%S%z')
            self.data.timeInterval['duration'] = int(self.data.timeInterval['duration'].total_seconds())
            logging.info("Schema validated successfully")
            return True
        except ValidationError as exc:
            logging.exception(exc)
            raise ValueError from exc
