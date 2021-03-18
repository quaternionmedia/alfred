from os import environ

PRODUCTION = environ.get('ALFRED_PRODUCTION')

DB_URL = environ.get('DB_URL')

CELERY_BROKER = environ.get('CELERY_BROKER')
CELERY_BACKEND = environ.get('CELERY_BACKEND')

BUCKET_NAME = environ.get('ALFRED_BUCKET_NAME', 'tower-renders')

EMAIL_USERNAME = environ.get('EMAIL_USERNAME')
EMAIL_PASSWORD = environ.get('EMAIL_PASSWORD')
EMAIL_SERVER = environ.get('EMAIL_SERVER')
EMAIL_PORT = environ.get('EMAIL_PORT')
EMAIL_SENDTO = environ.get('EMAIL_SENDTO').split(',')

INVOICE_EMAIL_BODY = '''Please find attached an invoice for this week's renders. If you have any questions, feel free to contact us.

Thanks!

~Alfred
alfred.quaternion.media
'''