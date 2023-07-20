from os import environ

if not environ.get('STATIC_DIR'):
    environ['STATIC_DIR'] = 'tests/dist'
