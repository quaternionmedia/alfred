from fastapi import APIRouter

# deprecated functions, to be removed
v1 = APIRouter()

def getEdl(filename='test.csv'):
    results = db.edls.find_one({'filename': filename})
    if results:
        return results['edl']
    else:
        if isfile(join('dist', filename)):
            with open(join('dist', filename), 'r') as f:
                return f.read()
                # return f.read().strip().split('\n')[1:]
        else:
            return False


@app.get('/edl')
def returnEdl(filename: str):
    return getEdl(filename)


@app.get('/edls')
def getEdls(user: User = Depends(get_current_active_user)):
    return [i['filename'] for i in db.edls.find({}, ['filename'])]