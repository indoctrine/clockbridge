import sys
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

class GoogleSheet:
    def __init__(self, id: str):
        self.spreadsheetId = id
        self.creds = None

    def authenticate(self, credsPath: str, scopes: list):
        try:
            if os.path.exists(credsPath):
                self.creds = service_account.Credentials.from_service_account_file(credsPath, scopes=scopes)
            return True
        except Exception as e:
            print(e, file=sys.stderr)

    def get_sheet_values(self, cellRange: str):
        result = self.sheet.values().get(spreadsheetId=self.spreadsheetId,
                                range=cellRange).execute()
        values = result.get('values', [])

        if not values:
            print('No data found.')

        return values
    
    def set_sheet_values(self, cellRange: str, dimension: str, values: list):
        body = {
            "majorDimension": dimension,
            'values': values
        }

        result = self.sheet.values().update(
                    spreadsheetId=self.spreadsheetId, range=cellRange,
                    valueInputOption="USER_ENTERED", body=body).execute()
        
        return result
        
    def build_service(self):
        try:
            service = build('sheets', 'v4', credentials=self.creds)
            self.sheet = service.spreadsheets()          
            return True
        except Exception as e:
            print(e, file=sys.stderr)
