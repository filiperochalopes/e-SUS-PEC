from __future__ import print_function
from datetime import datetime

import os
import sys
from flask import Flask, request

import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

CRON_PORT = int(os.getenv('CRON_PORT', 89))

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly',
          'https://www.googleapis.com/auth/drive.file']


now = datetime.now()
filename = f'{now.strftime("%Y_%m_%d_%H_%M_%S")}.backup'

DATABASE_HOST = os.getenv('POSTGRES_HOST', 'psql')
DATABASE_NAME = os.getenv('POSTGRES_DB', 'esus')
DATABASE_USER = os.getenv('POSTGRES_USER', 'postgres')

google_drive_folder_id = '1osoeAhww2IM2V2W_xbgcRoROHEk_DAPw' 


def get_google_credentials():
    """Authenticates at Google API"""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.join(os.path.dirname(__file__), 'credentials.json'), SCOPES)
            creds = flow.run_local_server(
                host='localhost', port=CRON_PORT, open_browser=True)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return creds


app = Flask(__name__)


@app.route("/")
def home():
    code = request.args.get('code')
    flow = InstalledAppFlow.from_client_secrets_file(
                os.path.join(os.path.dirname(__file__), 'credentials.json'), SCOPES, redirect_uri='/api/v1/backup-database')
    flow.fetch_token(code=code, include_client_id=True)
    return  code

@app.route("/backup-database")
def backup_database():
    from sh import pg_dump

    print(os.path.join(os.path.dirname(__file__)), file=sys.stderr)
    print(os.path.join(os.path.dirname(__file__),
          'credentials.json'), file=sys.stderr)

    print('Realizando backup do banco de dados...', file=sys.stderr)
    pg_dump('--host', DATABASE_HOST, '--port', '5432', '-U', DATABASE_USER, '-w', '--format', 'custom', '--blobs', '--encoding',
            'UTF8', '--no-privileges', '--no-tablespaces', '--no-unlogged-table-data', '--file', f'/home/{filename}', DATABASE_NAME)

    # Google Drive service
    service = build('drive', 'v3', credentials=get_google_credentials())

    print("Folder ID:", google_drive_folder_id)
    # upload a file text file
    # first, define file metadata, such as the name and the parent folder ID
    file_metadata = {
        "name": filename,
        "parents": [google_drive_folder_id]
    }

    # upload
    media = MediaFileUpload(f'/home/{filename}', resumable=True)
    file = service.files().create(body=file_metadata,
                                  media_body=media, fields='id').execute()
    print("File created, id:", file.get("id"))

    return None

if __name__ == '__main__':
    get_google_credentials()
