"""The set of render templates this control plane will accept.

The frontend's media bin has always asked for a template list -- `Bin.js` calls
it on init -- and no such route has ever existed, so the request 404'd and the
template bin rendered empty.

The list is an **explicit allowlist**, not `dir(otto.templates)`. That matters
beyond tidiness. `generateEdl` resolves a clip's template with
`getattr(templates, clip.name)` on a name that arrives from the client, and the
module namespace holds fourteen callables, of which six are templates; the rest
are imports it happens to carry -- `ColorClip`, `concatenate_videoclips`,
`rgbToDec` and friends. Publishing the namespace would advertise those as
templates, and validating against the namespace would bless them as input.

Keeping the allowlist here rather than in `otto` follows the control-plane
seam: which templates a caller may ask for is an API question, not a rendering
one. `otto` stays the thing that knows how to draw them.
"""

import inspect

from fastapi import APIRouter
from pydantic import BaseModel

from otto import templates as otto_templates

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

# `final` is deliberately absent, and it is the interesting case.
#
# It requires `address`, `website` and `phone` -- it raises KeyError without
# them -- and `TemplateData`, the only thing a clip's `data` can be, models
# none of the three. Pydantic drops unknown keys silently, so those values
# cannot reach the template through an EDL or through the preview endpoint no
# matter what a caller sends. It is structurally undrivable through this API.
#
# otto's own docstring marks it DEPRICATED, so the fix is to stop advertising
# it rather than to widen TemplateData for a template that is on the way out.
# Advertising a template that cannot be driven is worse than omitting one:
# every attempt fails as "A clip did not get made properly", which reads as a
# bug in the caller's data.
UNDRIVABLE_TEMPLATES = ('final',)

# Parameters every template takes from the engine rather than from the caller.
# Excluded from the advertised parameter list so the bin does not offer a field
# for something the caller does not supply.
_ENGINE_SUPPLIED = frozenset({'clipsize', 'duration', 'data', 'kwargs'})


class Template(BaseModel):
    name: str
    description: str
    parameters: list[str]
    deprecated: bool


def _describe(name):
    fn = getattr(otto_templates, name, None)
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
        description=summary,
        parameters=params,
        # otto spells it DEPRICATED. Match what is actually written rather
        # than what it should say, and accept both so a later fix upstream
        # does not silently un-deprecate five templates.
        deprecated='DEPRICATED' in doc.upper() or 'DEPRECATED' in doc.upper(),
    )


def available_templates():
    """Every allowlisted name that the installed engine actually provides.

    Skips names the engine does not have rather than failing the request: a
    version of otto without one template should still let the bin show the
    others. `test_every_advertised_template_exists` is what turns that
    silence into a failure at test time instead.
    """
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

    Where a finished render may be sent. The editor builds its choices from
    this rather than hardcoding them, so a destination becoming available is a
    server change, not a frontend release.
    """
    from ..utils.destinations import OFFERED_DESTINATIONS

    return list(OFFERED_DESTINATIONS)
