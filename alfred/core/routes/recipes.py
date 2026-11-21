"""Recipes: read them, write them.

`GET /recipes` lists the built-in recipes every account has and the caller's
own; `POST /recipes` stores one of the caller's, `PUT /recipes/{id}` replaces
it, `GET /recipes/{id}` reads one. A built-in recipe is read by its name and
cannot be written: an account that wants a changed one stores a copy.

Scoped to the caller as projects are (`utils.ownership`): another account's
recipe answers 404, exactly as one that does not exist. The routes reach
MongoDB only through `RecipeStore`, so a test can stand in for it; the
recipe's rules are the model's (`models.recipes.check_recipe`), raised here
as refusals by code.
"""

from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..errors import Code, Refusal
from ..models.recipes import Recipe, RecipeError, check_recipe
from ..utils.bucket import INVALID_ID, fresh
from ..utils.db import User
from ..utils.ownership import owner_filter, owner_key
from ..utils.recipes_builtin import BUILTIN, BY_NAME
from .users import current_active_user

OWNER = 'owner'


class RecipeView(BaseModel):
    """A recipe as the routes answer it: a built-in one by its name, a
    stored one by its id."""

    id: str
    name: str
    label: str
    description: str
    fields: List[dict]
    steps: List[dict]
    builtin: bool


class RecipeStore:
    """The recipe collection, as these routes use it."""

    def _recipes(self):
        return Recipe.get_motor_collection()

    async def list(self, query: dict) -> List[dict]:
        return await self._recipes().find(query).sort('name').to_list(500)

    async def find(self, query: dict) -> Optional[dict]:
        return await self._recipes().find_one(query)

    async def insert(self, document: dict) -> ObjectId:
        result = await self._recipes().insert_one(document)
        return result.inserted_id

    async def replace(self, recipe_id, fields: dict) -> None:
        await self._recipes().update_one({'_id': recipe_id}, {'$set': fields})


def get_recipe_store() -> RecipeStore:
    return RecipeStore()


def view_of(document: dict) -> RecipeView:
    return RecipeView(
        id=str(document.get('_id') or document['name']),
        name=document['name'],
        label=document.get('label') or document['name'],
        description=document.get('description') or '',
        fields=document.get('fields') or [],
        steps=document['steps'],
        builtin=document.get('_id') is None,
    )


def checked(body) -> dict:
    """`body` as a recipe, or a refusal by code: `unknown_operation` for a
    step naming none, `recipe_refused` for any other rule."""
    try:
        return check_recipe(body)
    except RecipeError as exc:
        code = (
            Code.UNKNOWN_OPERATION
            if 'is not an operation' in str(exc)
            else Code.RECIPE_REFUSED
        )
        raise Refusal(code, str(exc)) from exc


async def find_recipe(store: RecipeStore, reference: str, user) -> dict:
    """The recipe `reference` names, a built-in by its name or one of the
    caller's by its id; 404 `unknown_recipe` otherwise."""
    if reference in BY_NAME:
        return dict(BY_NAME[reference])
    if ObjectId.is_valid(reference):
        found = await store.find(
            {'_id': ObjectId(reference), **owner_filter(user, OWNER)}
        )
        if found is not None:
            return found
    raise Refusal(
        Code.UNKNOWN_RECIPE,
        f'No recipe is named {reference!r}: the built-in ones are '
        f'{", ".join(BY_NAME)}, and yours are listed by GET /recipes.',
    )


recipesAPI = APIRouter()


@recipesAPI.get('/recipes', response_model=List[RecipeView])
async def listRecipes(
    user: User = Depends(current_active_user),
    store: RecipeStore = Depends(get_recipe_store),
):
    """# The recipes

    The built-in recipes, each with `builtin: true` and its name as its id,
    then the caller's own by name. Each carries `fields`, which the Sculpt
    stage draws as a form project's, and `steps`, the operations it runs;
    docs/drafts.md lists the operations.
    """
    mine = await store.list(owner_filter(user, OWNER))
    return [view_of(r) for r in BUILTIN] + [view_of(r) for r in mine]


@recipesAPI.post(
    '/recipes',
    response_model=RecipeView,
    responses={422: {'description': 'not a recipe that can run; detail says the rule'}},
)
async def createRecipe(
    body: dict,
    user: User = Depends(current_active_user),
    store: RecipeStore = Depends(get_recipe_store),
):
    """# Store a recipe

    `{name, label, description, fields, steps}`: `name` a word, `fields` as
    a form project declares them, `steps` a list of `{op, ...parameters}`,
    each parameter a value in its range or `{"var": <field name>}`. Owned by
    the caller. 422 for a step naming no operation (`unknown_operation`) or
    any other rule broken (`recipe_refused`), the sentence naming the step.
    """
    recipe = checked(body)
    recipe[OWNER] = owner_key(user)
    recipe['_id'] = await store.insert(dict(recipe))
    return view_of(recipe)


@recipesAPI.get('/recipes/{item_id}', response_model=RecipeView)
async def getRecipe(
    item_id: str,
    user: User = Depends(current_active_user),
    store: RecipeStore = Depends(get_recipe_store),
):
    """# One recipe

    By a built-in recipe's name, or one of the caller's by its id; 404
    (`unknown_recipe`) otherwise.
    """
    return view_of(await find_recipe(store, item_id, user))


@recipesAPI.put('/recipes/{item_id}', response_model=RecipeView)
async def replaceRecipe(
    item_id: str,
    body: dict,
    user: User = Depends(current_active_user),
    store: RecipeStore = Depends(get_recipe_store),
):
    """# Replace a recipe of yours

    The whole recipe, as `POST /recipes` takes it. A built-in recipe cannot be
    replaced: store a copy under a name of your own. 404 (`unknown_recipe`)
    for a recipe that is not yours.
    """
    if not ObjectId.is_valid(item_id):
        raise fresh(INVALID_ID)
    found = await store.find({'_id': ObjectId(item_id), **owner_filter(user, OWNER)})
    if found is None:
        raise Refusal(Code.UNKNOWN_RECIPE, 'No recipe of yours has that id.')
    recipe = checked(body)
    await store.replace(found['_id'], recipe)
    return view_of({**found, **recipe})
