import schema

class Clockbridge:
    def verify_webhook_signature(self, request_headers, accepted_secrets):
        expected_keys = ['clockify-signature', 'clockify-webhook-event-type']
        headers = self.__normalise_headers(request_headers)
        if not headers:
            return False
        else:
            missing_headers = set(expected_keys).difference(headers.keys())
        if missing_headers:
            return False
        elif headers['clockify-signature'] in accepted_secrets:
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