from fastapi import APIRouter
from os.path import isfile
# deprecated functions, to be removed
v1 = APIRouter()

def seconds(t):
    return sum(x * round(float(s), 2) for x, s in zip([3600, 60, 1], t.split(":")))

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


@app.post('/form')
async def form_to_video(renderer: BackgroundTasks, form: VideoForm = Depends(VideoForm.as_form)):
    filename = f'{timestr()}_{form.project}.mp4'
    form.media = [ m.strip() for m in form.media.split(',') ]
    print('rendering video from form', form, filename)
    db.renders.insert_one(
        {'filename': filename,
        'form': dict(form),
        'progress': 0,
        'link': join('videos', filename),
        })
    renderer.add_task(renderForm, form=dict(form), filename=join('videos', filename), logger=DbLogger(filename))
    return filename

