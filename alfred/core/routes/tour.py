"""The tour's routes: the editor's journeys a stage at a time, each stage with its
feedback, and a person's word on a stage kept (alfred/tour.py).

`GET /tour` answers anyone: it is the editor's help. The words are kept and
served only where `ALFRED_TOUR_WORDS` is set (config.py); elsewhere both word
routes answer 403 saying so, and `GET /tour` says `words: false`. Words are
reached only through `TourWords`, so a test replaces the database with a list.
Saying the build asks git, which blocks, so it runs on the threadpool.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from alfred import tour
from alfred.config import TOUR_WORDS

from ..utils import get_db

tourAPI = APIRouter()

NOT_KEPT = (
    'This server keeps no words on the tour: only one started with '
    'ALFRED_TOUR_WORDS, which answers its own machine, does (docs/tour.md).'
)


class TourWords:
    """Every word kept, in the database's `TourWord` collection, oldest first."""

    collection = 'TourWord'

    async def add(self, record: dict) -> None:
        await get_db()[self.collection].insert_one(dict(record))

    async def all(self) -> List[dict]:
        cursor = get_db()[self.collection].find({}, {'_id': 0}).sort('_id', 1)
        return await cursor.to_list(None)


def tour_words() -> Optional[TourWords]:
    """Where words are kept, or None where this server keeps none."""
    return TourWords() if TOUR_WORDS else None


class Word(BaseModel):
    stage: str
    verdict: str
    note: str = ''
    by: str = ''


@tourAPI.get('/tour')
async def tour_document(words: Optional[TourWords] = Depends(tour_words)):
    """The journeys in their order, each stage with its line, what to try on it,
    what takes the editor there and the latest word on it, said of this build or
    an earlier one, and the commit the server runs."""
    return await run_in_threadpool(tour.document, await words.all() if words else None)


@tourAPI.get('/tour/feedback')
async def tour_feedback_kept(words: Optional[TourWords] = Depends(tour_words)):
    """Every word kept, oldest first: a stage, `works` or `off` with what is off,
    who said it, the moment, and the commit the server ran."""
    if words is None:
        raise HTTPException(status_code=403, detail=NOT_KEPT)
    return {'feedback': await words.all()}


@tourAPI.post('/tour/feedback', status_code=201)
async def tour_feedback(body: Word, words: Optional[TourWords] = Depends(tour_words)):
    """A person's word on one stage, under their name: `works`, or `off` saying
    what is off."""
    if words is None:
        raise HTTPException(status_code=403, detail=NOT_KEPT)
    try:
        record = await run_in_threadpool(
            tour.word, body.stage, body.verdict, body.note, body.by
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except tour.Refused as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    await words.add(record)
    return record
