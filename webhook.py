"""
AUTHOR:     Beck D.
DATE:       2023-
PURPOSE:    This module handles validating the incoming payload for Clockbridge
"""

import logging
import sys
from payload import Payload

class Webhook:
    """Overarching class where the magic happens"""
    def __init__(self, config):
        self.config = config
        self.action = None

        logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    stream=sys.stderr,level=f"logging.{self.config.log_level}")

    def verify_incoming_webhook(self, payload):
        """Verify signature and payload"""
        headers = payload.headers
        data = payload.data
        verify_payload = self.verify_payload(data)
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
                logging.debug("Required headers are missing!")
                return False
        else:
            return False

        if (headers['clockify-signature'] in self.config.webhook_secrets and
            headers['clockify-webhook-event-type'].casefold() in self.config.event_types):
            self.action = headers['clockify-webhook-event-type']
            logging.debug("All expected headers are present, continuing...")
            return True
        return False

    def __normalise_headers(self, request_headers):
        """Normalise (Casefold) the headers so that they can be validated"""
        try:
            headers = dict(request_headers)
            logging.debug("Forcing headers to lowercase")
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
            return dict(payload.data)
        except Exception as exc:
            raise ValueError("Malformed payload") from exc
