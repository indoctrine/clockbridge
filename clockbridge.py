import schema
import json

class Clockbridge:
    def __init__(self, config):
        self.config = config

    def verify_incoming_webhook(self, headers, payload):
        verify_payload = self.verify_webhook_payload(payload)
        if self.verify_webhook_signature(headers) and verify_payload:
            return verify_payload
        else:
            return False

    def verify_webhook_signature(self, request_headers):
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
        except ValueError as e:
            return None
        
    def verify_webhook_payload(self, payload):
        try:
            parsed_payload = json.loads(payload)
        except:
            return False
        payload_schema = schema.Schema(
            {
                "id": str,
                "description": str,
                "userId": str,
                "projectId": str,
                "timeInterval": {
                "start": str,
                "end": str,
                "duration": str,
                },
                "project": {
                    "name": str,
                    "clientId": str,
                    "workspaceId": str,
                    "estimate": {
                        "estimate": str,
                        "type": str
                    },
                "clientName": str,
                },
            }, ignore_extra_keys=True)

        validated_payload = payload_schema.validate(parsed_payload)
        return validated_payload