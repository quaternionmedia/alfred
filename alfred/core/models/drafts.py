"""What a draft carries of where it came from, and a source's record of the
job that made its drafts.

A draft is a project (`models.project.Project`) with `source` set: the
project it was cut from, the recipe and the values it ran with, the spans of
the source it took and the scores it was chosen by. `drafts_job` sits on the
source: the last run of recipes over it, where it got to and, when it
failed, why, as `captions_job` records a transcription. `drafts_dropped`
sits on the source too: what it keeps of each draft dropped from it, so a
recipe's first values can be measured against what people keep and drop
(`utils.measured`) after the drafts themselves are gone.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

# Whose cues the drafts are on their source (`PUT /project/{id}/cues`).
CUE_SOURCE = 'alfred-drafts'
CUE_KIND = 'draft'


class DraftSource(BaseModel):
    """Where a draft came from."""

    # The source project's id.
    project: str
    # The recipe's name, built in, or id, stored.
    recipe: str
    values: dict = {}
    # The spans of the source the draft took, each `[start, end]`.
    spans: List[List[float]] = []
    scores: dict = {}
    made_at: Optional[datetime] = None


class DroppedDraft(BaseModel):
    """What a source keeps of a draft dropped from it: its provenance, as the
    draft carried it, and how long its timeline was when it went."""

    id: str
    name: Optional[str] = None
    recipe: str
    values: dict = {}
    spans: List[List[float]] = []
    scores: dict = {}
    made_at: Optional[datetime] = None
    # The draft's timeline length when it was dropped, in seconds.
    duration: Optional[float] = None
    dropped_at: Optional[datetime] = None


DraftsState = Literal['queued', 'running', 'done', 'failed']

# The states in which a run is still under way.
RUNNING = ('queued', 'running')


class DraftsJob(BaseModel):
    """The last run of recipes over a source."""

    state: DraftsState
    error: Optional[str] = None
    # The recipes asked for, by name or id.
    recipes: List[str] = []
    # How many drafts the run left, once done.
    made: Optional[int] = None
    # What the run had to say: a step skipped, a file not measured.
    notes: List[str] = []
    updated_at: Optional[datetime] = None
