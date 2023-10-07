import json
import Clockify
from GoogleSheet import GoogleSheet
from datetime import datetime, timedelta
from flask import Flask, Response, request

file_path = os.environ.get('CLOCKBRIDGE_CONFIG_PATH')
if not file_path:
    file_path = '/opt/clockbridge/config.yaml'

app = Flask(__name__)
config = Config(file_path)

    return timedelta(hours=hour, minutes=min)

def create_app():
    app = Flask(__name__)
    return app

flaskApp = create_app()

@flaskApp.route("/webhook/clockify", methods = ['POST'])
def webhook_receive():
    # Token is sent in Clockify-Signature header - can use this to verify requests and lockdown my endpoint

    hook = Clockify.Webhook()
    requestVerified = hook.verify_signature(dict(request.headers), 'secrets/webhook-secrets.json')
    
    if requestVerified:
        payload = json.loads(request.data)

        if payload['project']['clientName'] == 'Drawing':
            startDate = datetime.strptime(payload['timeInterval']['start'], "%Y-%m-%dT%H:%M:%SZ")
            endDate = datetime.strptime(payload['timeInterval']['end'], "%Y-%m-%dT%H:%M:%SZ")
            clockifyDuration = calc_timedelta(startDate, endDate)
            dayOfYear = endDate.timetuple().tm_yday # Get day of the year
            
            sheetCellRange = f'{endDate.year}!B{dayOfYear+1}' # Allow for header row
            sheet = GoogleSheet(id='1F0l7fuqEO8jvGXu0yaaq7jvrGgqubYS3iCwjgXSkuiY')
            sheet.authenticate(credsPath='secrets/credentials.json', scopes=['https://www.googleapis.com/auth/spreadsheets'])
            sheet.build_service()
            sheetValues = sheet.get_sheet_values(cellRange=sheetCellRange)

            if sheetValues:
                sheetTime = datetime.strptime(sheetValues[0][0], '%H:%M:%S')
            else:
                sheetTime = datetime.strptime("00:00:00", "%H:%M:%S")
            
            sheetDuration = timedelta(hours=sheetTime.hour, minutes=sheetTime.minute)
            totalDuration = str(clockifyDuration + sheetDuration)

            result = sheet.set_sheet_values(cellRange=sheetCellRange, dimension="COLUMNS", values=[[totalDuration]])
            
            return json.dumps(result)
        else:
            return Response("Nothing to process", 200)
    else:
        return Response("Authentication required", 401)
