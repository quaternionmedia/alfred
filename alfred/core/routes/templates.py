"""The render templates this server offers and accepts: an allowlist.

Narrower than otto's registry (`otto.templates.TEMPLATES`), which is what the
engine draws; never `dir(otto.templates)`, which holds helpers too. Which
templates a caller may ask for is an API question, so it is answered here.
See docs/api/otto.md#get-templates.
"""

import inspect

from fastapi import APIRouter
from otto import templates as otto_templates
from pydantic import BaseModel

templateAPI = APIRouter()


# Ordered for display: the two current templates first, then the ones whose
# docstrings mark them deprecated, then the colour fill.
TEMPLATE_NAMES = (
    'title',
    'textBox',
    'bullets',
    'initial',
    'makeColor',
)

# What the editor calls each template; a name without one is shown as it is.
TEMPLATE_LABELS = {
    'title': 'Title',
    'textBox': 'Text box',
    'bullets': 'Bullets',
    'initial': 'Initial screen',
    'makeColor': 'Colour',
}

# For templates whose otto docstring is empty.
FALLBACK_DESCRIPTIONS = {
    'makeColor': 'Fill the frame with one colour',
}

# Not offered: `final` would draw otto's placeholder address and website,
# which no field of `TemplateData` can change. Deprecated in otto.
UNDRIVABLE_TEMPLATES = ('final',)

# Parameters the engine supplies, so not advertised to the caller.
_ENGINE_SUPPLIED = frozenset({'clipsize', 'duration', 'data', 'kwargs'})


class Template(BaseModel):
    name: str
    # What the editor shows; `name` is what a clip carries and is validated.
    label: str
    description: str
    parameters: list[str]
    deprecated: bool


def _describe(name):
    # From the registry, not the module's namespace.
    fn = otto_templates.TEMPLATES.get(name)
    if fn is None or not callable(fn):
        return None
    doc = inspect.getdoc(fn) or ''
    summary = doc.split('\n')[0].strip()
    try:
        params = [
            p
            for p in inspect.signature(fn).parameters
            if p not in _ENGINE_SUPPLIED and not p.startswith('*')
        ]
    except (TypeError, ValueError):
        params = []
    return Template(
        name=name,
        label=TEMPLATE_LABELS.get(name, name),
        description=summary or FALLBACK_DESCRIPTIONS.get(name, ''),
        parameters=params,
        # otto spells it DEPRICATED; both spellings, for when it is fixed.
        deprecated='DEPRICATED' in doc.upper() or 'DEPRECATED' in doc.upper(),
    )


def available_templates():
    """Every allowlisted name the installed engine provides. One it lacks is
    skipped, not an error; a test fails on it instead
    (`test_every_advertised_template_is_in_the_engine_s_registry`)."""
    described = (_describe(name) for name in TEMPLATE_NAMES)
    return [t for t in described if t is not None]


@templateAPI.get('/templates', response_model=list[Template])
async def listTemplates():
    """# Templates

    The render templates this server accepts, with the parameters each takes.
    Used by the editor's media bin; also the set a clip's `name` is validated
    against when `type` is `template`.
    """
    return available_templates()


@templateAPI.get('/destinations', response_model=list[str])
async def listDestinations():
    """# Destinations

    Where a finished render may be sent: the editor's choices.
    """
    from ..utils.destinations import OFFERED_DESTINATIONS

    return list(OFFERED_DESTINATIONS)
