"""
AUTHOR:     Beck D.
DATE:       2023-
PURPOSE:    This module handles validating the incoming payload for Clockbridge
"""

from payload import Payload
import json

class Webhook:
    """Overarching class where the magic happens"""
    def __init__(self, config):
        self.config = config

    def verify_incoming_webhook(self, headers, payload):
        """Verify signature and payload"""
        verify_payload = self.verify_payload(payload)
        if self.verify_signature(headers) and verify_payload:
            return verify_payload
        return False

    def verify_signature(self, request_headers):
        """Verify the webhook headers contain correct signature"""
        expected_keys = ['clockify-signature', 'clockify-webhook-event-type']
        headers = self.__normalise_headers(request_headers)
        if headers:
            missing_headers = set(expected_keys).difference(headers.keys())
            if missing_headers:
                return False
        if (headers['clockify-signature'] in self.config.webhook_secrets and 
            headers['clockify-webhook-event-type'].casefold() in self.config.event_types):
            return True
        return False

    def __normalise_headers(self, request_headers):
        """Normalise (Casefold) the headers so that they can be validated"""
        try:
            headers = dict(request_headers)
            for header_key, header in dict(request_headers).items():
                headers[header_key.casefold()] = header
                headers.pop(header_key)
            return headers
        except ValueError:
            return None

    def verify_payload(self, data):
        """Validate the payload against the schema"""
        try:
            payload = Payload(data)
            payload.validate_schema()
            return payload.data
        except Exception as exc:
            raise ValueError("Malformed payload") from exc
