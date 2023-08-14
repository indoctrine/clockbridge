import clockbridgeconfig
import schema

class Clockbridge:
    def verify_webhook_signature(self, headers):
        expected_keys = ['clockify-signature', 'clockify-webhook-event-type']
        headers = dict(headers)
        header_keys = [x.casefold() for x in headers.keys()]
        missing_headers = set(expected_keys).difference(header_keys)

        if missing_headers:
            return False
        
        if len(headers['Clockify-Signature']) == 32:
            return True
        else:
            return False