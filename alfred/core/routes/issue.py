from fastapi import APIRouter, Body, HTTPException
from ..utils import sendMail
from alfred.config import EMAIL_SENDTO

issueAPI = APIRouter()


@issueAPI.post('/{item_id}/report')
async def reportIssue(item_id: str, issue: str = Body(...)):
    """# Report issue
    Reports an issue with a specific render. Sends an email to the support team
    """
    if not sendMail(
        recepients=EMAIL_SENDTO, subject=f'issue with render: {item_id}', message=issue
    ):
        print('error reporting issue with ', item_id, issue)
        raise HTTPException(status_code=500, detail='error sending email')
