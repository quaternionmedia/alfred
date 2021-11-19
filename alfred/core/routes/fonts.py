from fastapi import APIRouter
from ..utils.db import db

fontAPI = APIRouter()

@fontAPI.get('/fonts')
async def getFonts():
    """# Get fonts
    Returns a list of all available fonts available to be rendered on this instance"""
    return [i['family'] for i in await db.fonts.find({}, ['family']).to_list(1000)]
