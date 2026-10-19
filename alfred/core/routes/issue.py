from fastapi import APIRouter, Body, Depends
from starlette.concurrency import run_in_threadpool

from ..models import UserRead as User
from ..utils.support_mail import (
    MailQueued,
    get_mail_queue,
    queue_mail,
    refuse_unless_configured,
)
from .render import RenderStore, get_render_store, load_owned_render
from .users import current_active_user

issueAPI = APIRouter()


@issueAPI.post(
    '/{item_id}/report',
    status_code=202,
    response_model=MailQueued,
    responses={
        404: {'description': 'no such render, or not yours'},
        503: {'description': 'no mail set up on this server, or the queue is down'},
    },
)
async def reportIssue(
    item_id: str,
    issue: str = Body(...),
    user: User = Depends(current_active_user),
    store: RenderStore = Depends(get_render_store),
    queue=Depends(get_mail_queue),
):
    """# Report issue
    Reports an issue with one of the caller's renders, by mail to the support
    team (EMAIL_SENDTO).

    Answers 202 once the mail is queued, with the worker's `job` id; the
    worker sends it, and tries again for a while if the mail server is down.
    503 when the server has no mail set up, or the queue will not take it.

    The render has to be one the caller may see -- their own, or any for a
    superuser -- and is looked up the way every other render route looks one
    up: 422 for a malformed id, 404 otherwise. This route took any id, so
    anyone signed in could have the server mail support about somebody else's
    render, or about one that did not exist.
    """
    await load_owned_render(store, item_id, user)
    refuse_unless_configured()
    # Queued, not sent: the mail went out over SMTP from here, with no
    # timeout, and the request waited for the mail server -- or, with one
    # that never replied, for as long as the connection held. Off the event
    # loop, as every send to the broker is.
    return await run_in_threadpool(
        queue_mail,
        queue,
        about=f'an issue with render {item_id}',
        subject=f'issue with render: {item_id}',
        message=issue,
    )
