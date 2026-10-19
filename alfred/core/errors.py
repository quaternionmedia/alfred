"""Why alfred refused a request, in a word a program can switch on.

A refusal alfred's own routes raise answers

    {"detail": "<a sentence for a person>", "code": "<a word for a program>"}

`detail` is the sentence it always was -- the editor shows it, and every
client that reads it reads it unchanged -- and `code`, beside it, is one of
`Code`: what the refusal means, which the sentence says only in words. Two
refusals with one status, such as the two 503s a transcription can meet, are
told apart by their codes, not by matching their wording, which is free to
change.

Each code has one status (`REFUSALS`), so a `Refusal` is built from its code
and its sentence and cannot answer a status its code does not mean.
docs/api/errors.md lists every code, and tests/unit/test_refusal_codes.py
holds that table to `REFUSALS`, every code to a route that answers it, and
the routes it covers to raising nothing without one.

What answers without a code: FastAPI's 422 for a request its model refuses,
whose `detail` is a list that already says where and what; the sign-in and
account routes, whose fastapi-users `detail` is itself a code; a request
without a session (401); and the routes the table says are not covered yet.
"""

from enum import StrEnum
from typing import Mapping, NamedTuple, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse


class Code(StrEnum):
    """What a refusal means. The values are the API's: never rename one."""

    # Any route that takes an id.
    INVALID_ID = 'invalid_id'
    NOT_FOUND = 'not_found'
    # Captions, and transcribing them.
    TOO_MANY_CAPTIONS = 'too_many_captions'
    CAPTION_FILE_UNREADABLE = 'caption_file_unreadable'
    AUDIO_ENGINE_MISSING = 'audio_engine_missing'
    TIMELINE_EMPTY = 'timeline_empty'
    TIMELINE_UNPLAYABLE = 'timeline_unplayable'
    TIMELINE_SILENT = 'timeline_silent'
    TRANSCRIPTION_RUNNING = 'transcription_running'
    TRANSCRIPTION_NOT_QUEUED = 'transcription_not_queued'
    # Renders: queueing one, and getting it back.
    ENCODER_OPTIONS_REFUSED = 'encoder_options_refused'
    FRAME_SIZE_OUT_OF_RANGE = 'frame_size_out_of_range'
    FPS_OUT_OF_RANGE = 'fps_out_of_range'
    UNKNOWN_QUALITY = 'unknown_quality'
    EDL_REFUSED = 'edl_refused'
    RENDER_NOT_QUEUED = 'render_not_queued'
    RENDER_NOT_FINISHED = 'render_not_finished'
    DESTINATION_UNKNOWN = 'destination_unknown'
    DELIVERY_FAILED = 'delivery_failed'
    DELIVERED_WITHOUT_LINK = 'delivered_without_link'
    CLOUD_LINK_UNAVAILABLE = 'cloud_link_unavailable'


class Meaning(NamedTuple):
    status: int
    means: str


# Each code's status, and what it means, in the words docs/api/errors.md uses.
REFUSALS: Mapping[Code, Meaning] = {
    Code.INVALID_ID: Meaning(422, 'the id in the path is not an id'),
    Code.NOT_FOUND: Meaning(404, 'no such item, or not yours'),
    Code.TOO_MANY_CAPTIONS: Meaning(422, 'more captions than a project carries'),
    Code.CAPTION_FILE_UNREADABLE: Meaning(422, 'the subtitle file cannot be read'),
    Code.AUDIO_ENGINE_MISSING: Meaning(503, 'no audio engine alfred can ask'),
    Code.TIMELINE_EMPTY: Meaning(422, 'no saved timeline to transcribe'),
    Code.TIMELINE_UNPLAYABLE: Meaning(422, 'the saved timeline cannot be played'),
    Code.TIMELINE_SILENT: Meaning(422, 'nothing in the timeline can make a sound'),
    Code.TRANSCRIPTION_RUNNING: Meaning(409, 'a transcription is under way'),
    Code.TRANSCRIPTION_NOT_QUEUED: Meaning(503, 'the broker would not take the job'),
    Code.ENCODER_OPTIONS_REFUSED: Meaning(422, 'encoder options, not a quality'),
    Code.FRAME_SIZE_OUT_OF_RANGE: Meaning(422, 'a width or height out of range'),
    Code.FPS_OUT_OF_RANGE: Meaning(422, 'a frame rate out of range'),
    Code.UNKNOWN_QUALITY: Meaning(422, 'not one of the qualities'),
    Code.EDL_REFUSED: Meaning(422, 'a clip this server will not render'),
    Code.RENDER_NOT_QUEUED: Meaning(503, 'the broker would not take the render'),
    Code.RENDER_NOT_FINISHED: Meaning(409, 'the render has no finished file yet'),
    Code.DESTINATION_UNKNOWN: Meaning(502, 'no destination of that name'),
    Code.DELIVERY_FAILED: Meaning(502, 'the destination would not take it'),
    Code.DELIVERED_WITHOUT_LINK: Meaning(502, 'uploaded, but no link was signed'),
    Code.CLOUD_LINK_UNAVAILABLE: Meaning(502, 'no cloud link can be signed'),
}


class Refusal(HTTPException):
    """A refusal that says why in a code as well as in words: answered as
    `{"detail", "code"}` (`answer_refusal`), with its code's status.

    Still an HTTPException, with a string `detail`, so code that catches or
    inspects one sees what it always saw.
    """

    def __init__(self, code: Code, detail: str, headers: Optional[dict] = None):
        code = Code(code)
        super().__init__(
            status_code=REFUSALS[code].status, detail=detail, headers=headers
        )
        self.code = code

    def again(self) -> 'Refusal':
        """A new refusal saying the same, to raise in place of a shared one
        (see `utils.bucket.fresh`)."""
        return Refusal(self.code, self.detail, headers=self.headers)

    def body(self) -> dict:
        return {'detail': self.detail, 'code': self.code.value}


async def answer_refusal(request, exc: Refusal) -> JSONResponse:
    return JSONResponse(exc.body(), status_code=exc.status_code, headers=exc.headers)


def install(app) -> None:
    """Answer every `Refusal` `app` raises with its code beside its detail."""
    app.add_exception_handler(Refusal, answer_refusal)
