from os import environ

PRODUCTION = environ.get('ALFRED_PRODUCTION')

SECRET_KEY = environ.get('ALFRED_SECRET_KEY')

DB_URL = environ.get('DB_URL')
DB_NAME = environ.get('DB_NAME', 'db')

CELERY_BROKER = environ.get('CELERY_BROKER')
CELERY_BACKEND = environ.get('CELERY_BACKEND')

BUCKET_NAME = environ.get('ALFRED_BUCKET_NAME', 'tower-renders')
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

EMAIL_USERNAME = environ.get('EMAIL_USERNAME')
EMAIL_PASSWORD = environ.get('EMAIL_PASSWORD')
EMAIL_SERVER = environ.get('EMAIL_SERVER')
EMAIL_PORT = environ.get('EMAIL_PORT')
EMAIL_SENDTO = environ.get('EMAIL_SENDTO')
if EMAIL_SENDTO:
    EMAIL_SENDTO = EMAIL_SENDTO.split(',')

INVOICE_EMAIL_BODY = '''Please find attached an invoice for this week's renders. 

If you have any questions, feel free to contact us.

Thanks!

~Alfred
alfred.quaternion.media
'''


class CeleryConfig:
    task_serializer = "pickle"
    result_serializer = "pickle"
    event_serializer = "json"
    accept_content = ["application/json", "application/x-python-serialize"]
    result_accept_content = ["application/json", "application/x-python-serialize"]
