import os
import sys
from flask import Flask

app = Flask(__name__)

@app.route("/backup-database")
def backup_database():
    from sh import pg_dump
    from datetime import datetime

    now = datetime.now()

    DATABASE_HOST = os.getenv('POSTGRES_HOST', 'psql')
    DATABASE_NAME = os.getenv('POSTGRES_DB', 'esus')
    DATABASE_USER = os.getenv('POSTGRES_USER', 'postgres')

    
    print('Realizando backup do banco de dados...', file=sys.stderr)
    pg_dump('--host', DATABASE_HOST, '--port', '5432', '-U', DATABASE_USER, '-w', '--format', 'custom', '--blobs', '--encoding', 'UTF8', '--no-privileges', '--no-tablespaces', '--no-unlogged-table-data', '--file', f'/home/{now.strftime("%Y_%m_%d_%H_%M_%S")}.backup', DATABASE_NAME)
        
    return "<p>Hello, World!</p>"