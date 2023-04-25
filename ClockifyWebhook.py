import json

class Webhook():
        def verify_signature(self, request, secretsFile):
            with open(secretsFile, 'r') as fp:
                secrets = json.load(fp)
                tokens = secrets['secrets']
                receivedToken = request.headers.get('Clockify-Signature')

                if receivedToken in tokens:
                     return True
                else:
                     return False