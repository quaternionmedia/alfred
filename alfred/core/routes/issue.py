from fastapi import APIRouter, Body
from ..utils import sendMail

issueAPI = APIRouter()

@issueAPI.post('/report')
async def reportIssue(name: str, issue: str = Body(...)):
    """# Report issue
    Reports an issue with a specific render. Sends an email to the support team for follow up."""
    if not sendMail(recepients=EMAIL_SENDTO, subject=name, message=issue):
        print('error reporting issue with ', name, issue)
        raise HTTPException(status_code=500, detail='error sending email')
