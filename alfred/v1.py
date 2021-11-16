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
    

@routes.get('/download')
async def download_file(filename: str):
    """# Download
    Download file from server
    
    *Depricated*
    """
    return FileResponse(filename, filename=filename)



@routes.post('/upload')
async def upload(file: UploadFile = File(...)):
    print('saving files', file.filename)
    await saveFile(file)
    return {'filename': join('data', file.filename)}

async def saveFile(file, location='data'):
    data = await file.read()
    with open(join(location, file.filename), 'wb') as f:
        f.write(data)


@routes.post('/save')
async def saveForm(project: str, form: VideoForm = Depends(VideoForm.as_form)):
    form.media = [ m.strip() for m in form.media.split(',') ]
    form.audio = [ m.strip() for m in form.audio.split(',') ]
    result = db.projects.update_one({'name': project}, {'$set': {'form': dict(form)}}, upsert=True)
    print('saved form', project, form, result)
    return result.modified_count

@routes.post('/formToEdl')
async def form_to_edl(form: VideoForm = Depends(VideoForm.as_form)):
    form.media = [ m.strip() for m in form.media.split(',') ]
    form.audio = [ m.strip() for m in form.audio.split(',') ]
    edl = formToEdl(form)
    print('edl from form', edl, dict(form))
    db.projects.update_one({'name': form.project},
        {'$set':
            {
                'form': dict(form),
                'edl': edl['edl'],
            }}, upsert=True)
    return True

@routes.get('/bkg/{project}')
async def get_bkg(project: str, width: int, height: int, t: float):
    clips = db.projects.find_one({'name': project}, ['form'])['form']['media']
    clip = download(clips[floor(t / 5)])
    print('making bkg', clip)
    try:
        if clip.endswith('mp4'):
            clip = VideoFileClip(clip)
        else:
            clip = ImageClip(clip)
        if width >= height:
            clip = clip.resize(width=width)
        else:
            clip = clip.resize(height=height)
        clip.save_frame('bkg.jpg', t=t % 5)
        return FileResponse('bkg.jpg')
    except Exception as e:
        print('error making kburns frame', e)
        raise HTTPException(status_code=500, detail='error making kburns frame')

@routes.post('/edl')
async def saveEdl(filename: str, edl: Edl):
    return dumps(db.edls.find_one_and_update({'filename': filename}, {'$set': {'edl': edl.clips}}, upsert=True, new=True))


@auth.post("/token", response_model=Token)
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    """# Login for access token
Accepts a username and password combination from a login form, and returns a JSON object with the auth credentials.

A special *mcguffic* cookie is created and stored in the database, to facilitate secure automatic login after a browser refresh."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise credentials_exception
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    mcguffin = token_urlsafe(32)
    db.mcguffins.insert_one({'name': mcguffin, 'username': user.username})
    response.set_cookie(key='mcguffin', value=mcguffin, httponly=True, secure=PRODUCTION)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token)


@auth.post('/refresh', response_model=Token)
async def refresh_access_token(response: Response, mcguffin: str = Cookie(None)):
    """# Refresh Access Token
If the user has not logged out, attempt to refresh login token automatically.

This checks for a stored browser cookie called "mcguffin", and verifies it against the database to confirm the session is valid, and the user has not yet logged out. If successful, it returns a new `Access Token` object, which can be used to access protected routes in the API.
    """
    try:
        token = db.mcguffins.find_one({'name': mcguffin})
        # print('refresh. checking mcguffin', mcguffin, token)
        if token:
            username: str = token['username']
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            # TODO update token status to 'used' instead of deleting
            db.mcguffins.delete_one({'name': mcguffin})
            mcguffin = token_urlsafe(32)
            db.mcguffins.insert_one({'name': mcguffin, 'username': username})
            response.set_cookie(key='mcguffin', value=mcguffin, httponly=True, secure=PRODUCTION)
            # print('making new token', username, access_token_expires, mcguffin)
            access_token = create_access_token(
                data={"sub": username}, expires_delta=access_token_expires
            )
            return Token(access_token=access_token)
        else:
            raise credentials_exception
    except Exception as e:
        print('error refreshing', e)
        raise credentials_exception