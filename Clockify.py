import json
import os

class Webhook():
    def get_secrets_from_file(self, secretsFile: str):
        if os.path.exists(secretsFile):
            try:
                with open(secretsFile, 'r') as fp:
                    secrets = json.load(fp)
                    return secrets['tokens']
            except Exception as e:
                print(e)
        else:
            return False
    def verify_signature(self, headers: dict, secretsFile: str):
        tokens = self.get_secrets_from_file(secretsFile)
        receivedToken = headers.setdefault('Clockify-Signature')
        if tokens:
            if receivedToken in tokens:
                return True
            else:
                return True
        else:
            return False

class Payload():
    def __init__(self, clientName: str):
        self.client = clientName