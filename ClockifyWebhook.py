import json

class ClockifyWebhook():
        def verify_signature(self, request, secretsFile)
            with open('webhook-secrets.json', 'r') as fp:
                secrets = json.load(fp)
                tokens = secrets['secrets']
                receivedToken = request.headers.get('Clockify-Signature')

                if receivedToken in tokens:
                     return True
                else:
                     return False