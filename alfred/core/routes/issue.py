from fastapi import APIRouter, Body, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from alfred.config import EMAIL_SENDTO

from ..models import UserRead as User
from ..utils import sendMail
from .render import RenderStore, get_render_store, load_owned_render
from .users import current_active_user

issueAPI = APIRouter()


@issueAPI.post('/{item_id}/report')
async def reportIssue(
    item_id: str,
    issue: str = Body(...),
    user: User = Depends(current_active_user),
    store: RenderStore = Depends(get_render_store),
):
    """# Report issue
    Reports an issue with one of the caller's renders. Sends an email to the
    support team.

    The render has to be one the caller may see -- their own, or any for a
    superuser -- and is looked up the way every other render route looks one
    up: 422 for a malformed id, 404 otherwise. This route took any id, so
    anyone signed in could have the server mail support about somebody else's
    render, or about one that did not exist.
    """
    await load_owned_render(store, item_id, user)
    # Off the event loop: the mail goes out over SMTP with no timeout, so the
    # api answered nothing else until the mail server had finished with it --
    # or, with one that never replied, for as long as the connection held.
    sent = await run_in_threadpool(
        sendMail,
        recepients=EMAIL_SENDTO,
        subject=f'issue with render: {item_id}',
        message=issue,
    )
    if not sent:
        print('error reporting issue with ', item_id, issue)
        raise HTTPException(status_code=500, detail='error sending email')
