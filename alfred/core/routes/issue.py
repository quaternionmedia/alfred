from fastapi import APIRouter, Body
from ..utils import sendMail

issueAPI = APIRouter()

@issueAPI.post('/{render}/report')
async def reportIssue(render: str, issue: str = Body(...)):
    """# Report issue
    Reports an issue with a specific render. Sends an email to the support team for follow up."""
    if not sendMail(recepients=EMAIL_SENDTO, subject=render, message=issue):
        print('error reporting issue with ', render, issue)
        raise HTTPException(status_code=500, detail='error sending email')
