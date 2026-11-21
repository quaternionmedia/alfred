"""Making a source's drafts: the worker's half of `POST /project/{id}/drafts`.

`make_drafts` takes the source project as stored, the recipes asked for with
their values, and the collections, and leaves one project per draft each
recipe made (`utils.sculpt.run`), with its captions and its words moved into
it, named for the source and the recipe, carrying `source`
(`models.drafts.DraftSource`); and on the source, a cue per span a draft
took, under the source `alfred-drafts`, so the Cues lane shows what each
draft took and a draft's cue is dropped with it.

The timeline's measures come from `utils.measures`, kept beside the library,
so a source measured once is measured once however many times recipes run
over it; a file that cannot be measured is a note, and the recipes run over
what there is.
"""

from datetime import datetime, timezone
from typing import List, Sequence, Tuple

from bson import ObjectId

from ..models.cues import Cue, checked_cues
from ..models.drafts import CUE_KIND, CUE_SOURCE
from ..models.recipes import RecipeError
from . import measures, sculpt
from .recipes_builtin import BY_NAME

# Where recipes are kept: beanie names the collection after the class.
RECIPES = 'Recipe'


class UnknownRecipe(LookupError):
    """No recipe of that name or id for this owner."""


def find_recipe(reference: str, owner, recipes) -> dict:
    """The recipe `reference` names: a built-in by its name, or one of the
    owner's by its id, from the `recipes` collection."""
    if reference in BY_NAME:
        return dict(BY_NAME[reference])
    if ObjectId.is_valid(reference):
        found = recipes.find_one({'_id': ObjectId(reference), 'owner': owner})
        if found is not None:
            return found
    raise UnknownRecipe(f'no recipe is named {reference!r}')


def draft_name(source_name, recipe_label, number) -> str:
    return f'{source_name or "source"} – {recipe_label} {number}'


def draft_document(
    source: dict, recipe: dict, values: dict, draft: sculpt.Draft, made_at
) -> dict:
    """A draft as a project the editor opens."""
    timeline = draft.timeline
    return {
        'name': draft_name(
            source.get('name'), recipe.get('label') or recipe['name'], draft.number
        ),
        'description': draft.description,
        'owner': source.get('owner'),
        'logic': {},
        'fields': [],
        'edl': {'clips': timeline['clips'], 'duration': timeline['duration']},
        'captions': timeline['captions'],
        'words': timeline['words'],
        # Drawn into renders only where the recipe said so.
        'caption_style': {
            **(source.get('caption_style') or {}),
            'enabled': draft.captions_drawn,
        },
        'render_settings': draft.render_settings or source.get('render_settings'),
        'destination': source.get('destination'),
        'source': {
            'project': str(source['_id']),
            'recipe': str(recipe.get('_id') or recipe['name']),
            'values': dict(values or {}),
            'spans': draft.spans,
            'scores': draft.scores,
            'made_at': made_at,
        },
    }


def cues_for(drafts: Sequence[Tuple[ObjectId, dict, dict]]) -> List[dict]:
    """A cue per span each draft took: `(id, document, recipe)` each."""
    cues = []
    for draft_id, document, _ in drafts:
        for start, end in document['source']['spans']:
            cues.append(
                Cue(
                    start=start,
                    end=end,
                    label=document['name'].split(' – ', 1)[-1],
                    kind=CUE_KIND,
                    state='made',
                    source=CUE_SOURCE,
                    ref=str(draft_id),
                    note=document.get('description') or None,
                ).model_dump()
            )
    return cues


def mark_source(source: dict, cues: List[dict], projects) -> None:
    """Replace the drafts' cues on the source with `cues`, keeping every
    other writer's."""
    kept = [c for c in (source.get('cues') or []) if c.get('source') != CUE_SOURCE]
    ordered = checked_cues([Cue.model_validate(c) for c in kept + cues])
    projects.update_one(
        {'_id': source['_id']}, {'$set': {'cues': [c.model_dump() for c in ordered]}}
    )


def make_drafts(
    source: dict, requests: Sequence[dict], projects, recipes
) -> Tuple[int, List[str]]:
    """Run each of `requests` (`{recipe, values}`) over `source`, insert the
    drafts into `projects`, mark the source, and return how many were made
    and the run's notes. UnknownRecipe and RecipeError say what stopped it."""
    chosen = [
        (
            find_recipe(str(r.get('recipe')), source.get('owner'), recipes),
            r.get('values') or {},
        )
        for r in requests
    ]
    clips = (source.get('edl') or {}).get('clips') or []
    measured = measures.timeline_measures(clips)
    notes = list(measured.notes)
    reading = sculpt.Source(
        clips=clips,
        captions=source.get('captions') or [],
        words=source.get('words') or [],
        levels=measured.levels,
        motion=measured.motion,
        silences=measured.silences,
    )
    made_at = datetime.now(timezone.utc)
    documents = []
    for recipe, values in chosen:
        try:
            run = sculpt.run(
                recipe['steps'], values, recipe.get('fields') or [], reading
            )
        except RecipeError as exc:
            raise RecipeError(f'{recipe["name"]}: {exc}') from exc
        notes.extend(f'{recipe["name"]}: {note}' for note in run.notes)
        for draft in run.drafts:
            documents.append(
                (draft_document(source, recipe, values, draft, made_at), recipe)
            )
    if documents:
        result = projects.insert_many([document for document, _ in documents])
        made = list(zip(result.inserted_ids, documents, strict=True))
        mark_source(
            source,
            cues_for(
                [(draft_id, document, recipe) for draft_id, (document, recipe) in made]
            ),
            projects,
        )
    return len(documents), notes
