from __future__ import print_function
from datetime import datetime

import os
import sys
from flask import Flask, Response

import os.path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from .env import BACKUP_EXPIRATION_TIME, DATABASE_HOST, DATABASE_NAME, DATABASE_USER, FILENAME, GOOGLE_DRIVE_FOLDER_ID, FILE_EXTENSION
from .googleoauth import get_google_credentials

app = Flask(__name__)

def get_file_in_path(filename):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), filename)

def upload_file(service, filename, mime_type, folder_id):
    try:
        file_metadata = {
                'name': filename,
                'parents': [folder_id],
                'mimeType': mime_type
            }

        media = MediaFileUpload(get_file_in_path(filename), mimetype=mime_type, resumable=True)

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
    except HttpError as error:
        print(f'An error occurred: {error}')
        file = None

    return file.get('id')

@app.route("/backup-database")
def backup_database():
    from sh import pg_dump

    print('Realizando backup do banco de dados...', file=sys.stderr)
    pg_dump('--host', DATABASE_HOST, '--port', '5432', '-U', DATABASE_USER, '-w', '--format', 'custom', '--blobs', '--encoding',
            'UTF8', '--no-privileges', '--no-tablespaces', '--no-unlogged-table-data', '--file', f'/home/{FILENAME}', DATABASE_NAME)

    
    # upload de arquivo
    print('Autenticando no Google...', file=sys.stderr)
    service = build('drive', 'v3', credentials=get_google_credentials())

    print('Realizando upload para Google Drive...', file=sys.stderr)
    file_id = upload_file(service=service, filename=FILENAME, mime_type='application/octet-stream', folder_id=GOOGLE_DRIVE_FOLDER_ID)
    print('File uploaded:', file_id)

    # Google Drive API: https://developers.google.com/drive/api/v3/reference
    print('Listando arquivos na pasta de backup...', file=sys.stderr)
    # fields props: https://developers.google.com/drive/api/v3/reference/files
    # query props: https://developers.google.com/drive/api/guides/search-files#python
    results = service.files().list(q=f'"{GOOGLE_DRIVE_FOLDER_ID}" in parents and trashed = false', orderBy='createdTime desc',
        pageSize=20, fields="nextPageToken, files(id, name, mimeType, description, trashed)").execute()
    items = results.get('files', [])

    if not items:
        print('No files found.', file=sys.stderr)
        return
    else:
        for item in items:
            print('{:<40} {:<20} {:<20}'.format(item['name'], item['mimeType'], item['trashed']), file=sys.stderr)

    print('Excluindo arquivos antigos...', file=sys.stderr)
    for item in items:
        filename_datetime = item['name'].replace(FILE_EXTENSION, '')
        try:
            print(datetime.now())
            print(BACKUP_EXPIRATION_TIME)
            if datetime.strptime(filename_datetime, '%Y_%m_%d_%H_%M_%S') < BACKUP_EXPIRATION_TIME:
                filename = f'{filename_datetime}{FILE_EXTENSION}'
                print(f'Excluindo {filename}', file=sys.stderr)
                os.remove(get_file_in_path(filename))
                service.files().delete(fileId=item['id']).execute()
        except Exception as e:
            print('error', e)

    return Response('Backup realizado', status=201)

if __name__ == '__main__':
    get_google_credentials()
