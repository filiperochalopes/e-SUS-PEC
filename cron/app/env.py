from datetime import datetime, timedelta
import os

DATABASE_HOST = os.getenv('POSTGRES_HOST', 'psql')
DATABASE_NAME = os.getenv('POSTGRES_DB', 'esus')
DATABASE_USER = os.getenv('POSTGRES_USER', 'postgres')

NOW = datetime.now()
FILE_EXTENSION = '.backup'
FILENAME = f'{NOW.strftime("%Y_%m_%d_%H_%M_%S")}{FILE_EXTENSION}'

GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID', '1osoeAhww2IM2V2W_xbgcRoROHEk_DAPw')
BACKUP_EXPIRATION_TIME = datetime.now() - timedelta(days=7)