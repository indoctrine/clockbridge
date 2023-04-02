import json
from GoogleSheet import GoogleSheet
from datetime import datetime, timedelta
from flask import Flask, Response, request

def calc_timedelta(start: datetime, end: datetime):    
    delta = end - start
    min, sec = divmod(delta.total_seconds(), 60)
    hour, min = divmod(min, 60)

    if sec > 30:
        min += 1

    return timedelta(hours=hour, minutes=min)

def create_app():
    app = Flask(__name__)
    return app

flaskApp = create_app()

@flaskApp.route("/")
def root():
    return "Hello World"

@flaskApp.route("/webhook", methods = ['POST'])
def webhook_receive():
    # Token is sent in Clockify-Signature header - can use this to verify requests and lockdown my endpoint
    with open('webhook-secrets.json', 'r') as fp:
        secrets = json.load(fp)
        tokens = secrets['secrets']
    token = request.headers.get('Clockify-Signature')
    
    if token in tokens:
        payload = json.loads(request.data)

        if payload['project']['clientName'] == 'Drawing':
            startDate = datetime.strptime(payload['timeInterval']['start'], "%Y-%m-%dT%H:%M:%SZ")
            endDate = datetime.strptime(payload['timeInterval']['end'], "%Y-%m-%dT%H:%M:%SZ")
            clockifyDuration = calc_timedelta(startDate, endDate)

            dayOfYear = endDate.timetuple().tm_yday # Get day of the year
            hookDateRange = f'{endDate.year}!B{dayOfYear+1}' # Allow for header row
            sheet = GoogleSheet(scope=['https://www.googleapis.com/auth/spreadsheets'], 
                                id='1F0l7fuqEO8jvGXu0yaaq7jvrGgqubYS3iCwjgXSkuiY')
            sheet.authenticate(tokenPath='token.json')
            sheet.build_service()
            sheetValues = sheet.get_sheet_values(cellRange=hookDateRange)
            sheetTime = datetime.strptime(sheetValues[0][0], '%H:%M:%S')
            sheetDuration = timedelta(hours=sheetTime.hour, minutes=sheetTime.minute)
            totalDuration = str(clockifyDuration + sheetDuration)

            result = sheet.set_sheet_values(cellRange=hookDateRange, dimension="COLUMNS", values=[[totalDuration]])
            
            return result
        else:
            return Response("Nothing to process", 200)
    else:
        return Response("Authentication required", 401)