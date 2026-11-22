"""The labeller: a chat model that sorts a stretch of a transcript into one
of a recipe's categories, and says how well it stands alone.

It is reached through ALFRED_LABELLER_URL, the base of an OpenAI-style chat
route: `POST <url>/chat/completions` with `{model, messages, max_tokens,
temperature}` answers `choices[0].message.content`, and `GET <url>/models`
lists what is served as `data[].id`. Any server speaking that route will do,
a local model server among them. alfred names no model: ALFRED_LABELLER_MODEL
is the one the route serves, and without it there is no labeller. Each
question is one short prompt over the stretch's words, cut to `LABEL_CHARS`,
answered in a few tokens at temperature zero: a category is read out of the
answer by name, the longest of the recipe's named in it, and a score as a
whole number from 0 to `SCALE`, scaled to 0 to 1.

`Labeller` is what `utils.sculpt` is handed, so the arithmetic reaches no
model itself: `category(text, categories)` and `alone(text)`, each one
request. `status()` is what `GET /health` reports. Every failure is a
`LabellerError` whose message is one line, so a job's notes can carry it.
"""

import re
from dataclasses import dataclass
from typing import Optional, Sequence
from urllib.parse import urlsplit, urlunsplit

import httpx

from ... import config

# How much of a stretch's text goes with a question.
LABEL_CHARS = 1200
# How many tokens an answer may run to: a category's name, or a number.
ANSWER_TOKENS = 16
# A failure's reason is one line of at most this many characters.
REASON_LIMIT = 300
# A score is asked for as a whole number up to this, and scaled to 0..1.
SCALE = 10
# The route's paths under the base address.
CHAT = '/chat/completions'
MODELS = '/models'

_NUMBER = re.compile(r'\d+(?:\.\d+)?')


class LabellerError(Exception):
    """The labeller could not do what was asked. The message is one line."""


class NoLabeller(LabellerError):
    """There is none to ask: no route, or no model, is configured."""


class LabellerFailed(LabellerError):
    """The labeller was asked and did not answer as the route promises."""


@dataclass(frozen=True)
class LabellerStatus:
    """`GET /health`'s `labeller`."""

    configured: bool
    ok: bool
    detail: Optional[str] = None


def labeller_url() -> Optional[str]:
    return config.LABELLER_URL


def model() -> Optional[str]:
    return config.LABELLER_MODEL


def describe(url=None) -> Optional[str]:
    """The route's address as it may be shown: no credentials, no query."""
    url = url if url is not None else labeller_url()
    if not url:
        return None
    parts = urlsplit(url)
    host = parts.hostname or ''
    if parts.port:
        host = f'{host}:{parts.port}'
    return urlunsplit((parts.scheme, host, parts.path.rstrip('/'), '', ''))


def problem() -> Optional[str]:
    """Why no labeller can be asked right now, or None when one can."""
    url = labeller_url()
    if not url:
        return (
            'No labeller is configured: set ALFRED_LABELLER_URL to the base of an '
            'OpenAI-style chat route and ALFRED_LABELLER_MODEL to the model it '
            'serves (docs/drafts.md says what is asked).'
        )
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return f'ALFRED_LABELLER_URL must be an http(s) URL, not {url!r}.'
    if not model():
        return (
            'ALFRED_LABELLER_MODEL names no model: alfred names none itself, so set '
            'it to one the labeller serves.'
        )
    return None


def _line(text, url=None) -> str:
    lines = str(text).strip().splitlines()
    line = lines[0].strip() if lines else ''
    where = describe(url)
    if where and where not in line:
        line = (
            f'the labeller at {where}: {line}'
            if line
            else f'the labeller at {where} failed'
        )
    if len(line) > REASON_LIMIT:
        line = line[: REASON_LIMIT - 3].rstrip() + '...'
    return line


def _client(transport=None) -> httpx.Client:
    return httpx.Client(
        base_url=labeller_url().rstrip('/'),
        timeout=config.LABELLER_TIMEOUT,
        transport=transport,
    )


# --- the questions -----------------------------------------------------------------


def category_prompt(text: str, categories: Sequence[str]) -> str:
    return (
        'Which one of these categories fits this stretch of a transcript best: '
        f'{", ".join(categories)}? Answer with the category alone.\n\n'
        f'{text[:LABEL_CHARS]}'
    )


def alone_prompt(text: str) -> str:
    return (
        'How well does this stretch of a transcript stand alone as a clip, with '
        'nothing before or after it: does it begin and end cleanly, and would a '
        f'viewer follow it? Answer with a whole number from 0 to {SCALE} alone, '
        f'{SCALE} for a clip that needs nothing around it.\n\n'
        f'{text[:LABEL_CHARS]}'
    )


def category_from(answer: str, categories: Sequence[str]) -> str:
    """The category `answer` names: the first of `categories`, longest first,
    found in it whatever the case; empty when it names none."""
    lowered = str(answer).lower()
    for category in sorted(categories, key=len, reverse=True):
        if category.lower() in lowered:
            return category
    return ''


def score_from(answer: str) -> Optional[float]:
    """The first number in `answer`, scaled from 0..SCALE to 0..1 and held in
    that range; None when it holds none."""
    found = _NUMBER.search(str(answer))
    if not found:
        return None
    return round(min(max(float(found.group()) / SCALE, 0.0), 1.0), 4)


# --- asking --------------------------------------------------------------------------


def ask(prompt: str, transport=None) -> str:
    """One question to the labeller, its answer as text. NoLabeller where none
    is configured; LabellerFailed where it does not answer as promised."""
    reason = problem()
    if reason:
        raise NoLabeller(reason)
    url = labeller_url()
    body = {
        'model': model(),
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': ANSWER_TOKENS,
        'temperature': 0,
    }
    try:
        with _client(transport) as client:
            response = client.post(CHAT, json=body)
    except httpx.HTTPError as exc:
        raise LabellerFailed(_line(f'{type(exc).__name__}: {exc}', url)) from exc
    if response.status_code >= 400:
        raise LabellerFailed(
            _line(f'it answered {response.status_code}: {response.text[:120]}', url)
        )
    try:
        content = response.json()['choices'][0]['message']['content']
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LabellerFailed(
            _line('its answer was not a chat completion with a message', url)
        ) from exc
    return str(content or '').strip()


class Labeller:
    """What `utils.sculpt` asks: one request a question. `transport` is a test's."""

    def __init__(self, transport=None):
        self.transport = transport

    def category(self, text: str, categories: Sequence[str]) -> str:
        """The one of `categories` the labeller sorts `text` into; empty where
        its answer names none, or where there are no categories to choose."""
        if not categories:
            return ''
        answer = ask(category_prompt(text, categories), self.transport)
        return category_from(answer, categories)

    def alone(self, text: str) -> Optional[float]:
        """How well `text` stands alone as a clip, 0 to 1; None where the
        answer holds no number."""
        return score_from(ask(alone_prompt(text), self.transport))


def _served(response) -> Optional[list]:
    """The model ids a `GET /models` answer lists, or None where its shape is
    not the route's, which is no failure: the route answered."""
    try:
        data = response.json().get('data')
    except (ValueError, AttributeError):
        return None
    if not isinstance(data, list):
        return None
    return [str(item.get('id')) for item in data if isinstance(item, dict)]


def status(transport=None) -> LabellerStatus:
    """Whether a labeller is configured, and whether it answers and serves the
    model named. Blocking."""
    configured = bool(labeller_url())
    reason = problem()
    if reason:
        return LabellerStatus(configured=configured, ok=False, detail=reason)
    try:
        with _client(transport) as client:
            response = client.get(MODELS)
    except httpx.HTTPError as exc:
        return LabellerStatus(True, False, _line(f'{type(exc).__name__}: {exc}'))
    if response.status_code >= 400:
        return LabellerStatus(True, False, _line(f'it answered {response.status_code}'))
    served = _served(response)
    if served is not None and model() not in served:
        return LabellerStatus(True, False, _line(f'it does not serve {model()}'))
    return LabellerStatus(configured=True, ok=True)
