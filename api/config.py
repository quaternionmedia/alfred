from os import environ

PRODUCTION = environ.get('ALFRED_PRODUCTION')

DB_URL = environ.get('DB_URL')

CELERY_BROKER = environ.get('CELERY_BROKER')
CELERY_BACKEND = environ.get('CELERY_BACKEND')

BUCKET_NAME = 'tower-bucket'
