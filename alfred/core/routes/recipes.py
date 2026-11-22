"""Recipes: read them, write them.

`GET /recipes` lists the built-in recipes every account has and the caller's
own; `POST /recipes` stores one of the caller's, `PUT /recipes/{id}` replaces
it, `DELETE /recipes/{id}` deletes it, `GET /recipes/{id}` reads one. A
built-in recipe is read by its name and cannot be written: an account that
wants a changed one stores a copy. `GET /recipes/operations` lists what a
step may name, with each operation's parameters, and `POST /recipes/check`
checks a recipe as a write would and stores nothing, so an editor can show
what a write would refuse before it writes.

Scoped to the caller as projects are (`utils.ownership`): another account's
recipe answers 404, exactly as one that does not exist. The routes reach
MongoDB only through `RecipeStore`, so a test can stand in for it; the
recipe's rules are the model's (`models.recipes.check_recipe`), raised here
as refusals by code.
"""

from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..errors import Code, Refusal
from ..models.recipes import OPERATIONS, Parameter, Recipe, RecipeError, check_recipe
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


class RecipeChecked(BaseModel):
    """A recipe as `POST /recipes` would store it: tidied, and nowhere yet."""

    name: str
    label: str
    description: str
    fields: List[dict]
    steps: List[dict]


class RecipeDeleted(BaseModel):
    deleted: str


class OperationView(BaseModel):
    """One operation a step may name, as `GET /recipes/operations` lists it."""

    name: str
    kind: str
    about: str
    # By parameter name: `{kind, default, low, high, choices}`, the bounds for
    # a number and the choices for a choice.
    parameters: Dict[str, Dict[str, Any]]


def parameter_view(parameter: Parameter) -> Dict[str, Any]:
    view: Dict[str, Any] = {'kind': parameter.kind, 'default': parameter.default}
    if parameter.low is not None:
        view['low'] = parameter.low
    if parameter.high is not None:
        view['high'] = parameter.high
    if parameter.choices:
        view['choices'] = list(parameter.choices)
    return view


OPERATION_VIEWS = [
    OperationView(
        name=name,
        kind=operation['kind'],
        about=operation['about'],
        parameters={
            key: parameter_view(parameter)
            for key, parameter in operation['parameters'].items()
        },
    )
    for name, operation in OPERATIONS.items()
]


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

    async def delete(self, recipe_id) -> int:
        result = await self._recipes().delete_one({'_id': recipe_id})
        return result.deleted_count


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


@recipesAPI.get('/recipes/operations', response_model=List[OperationView])
async def listOperations(user: User = Depends(current_active_user)):
    """# The operations

    Every operation a recipe's step may name, in the order their kinds run:
    its `kind`, what it does, and its parameters, each with its `kind`
    (`number`, `integer`, `boolean`, `text` or `choice`), its `default`, its
    `low` and `high` for a number and its `choices` for a choice.
    docs/drafts.md is the same table, for a person.
    """
    return OPERATION_VIEWS


@recipesAPI.post(
    '/recipes/check',
    response_model=RecipeChecked,
    responses={422: {'description': 'not a recipe that can run; detail says the rule'}},
)
async def checkRecipe(body: dict, user: User = Depends(current_active_user)):
    """# Check a recipe

    The recipe as `POST /recipes` takes it, checked by the same rules and
    refused by the same codes, the sentence naming the step; answered as it
    would be stored, tidied, and stored nowhere.
    """
    return RecipeChecked(**checked(body))


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


@recipesAPI.delete('/recipes/{item_id}', response_model=RecipeDeleted)
async def deleteRecipe(
    item_id: str,
    user: User = Depends(current_active_user),
    store: RecipeStore = Depends(get_recipe_store),
):
    """# Delete a recipe of yours

    By its id; answers `{deleted}`. A built-in recipe cannot be deleted, and
    its name is not an id (`invalid_id`); another account's is 404
    (`unknown_recipe`). A draft the recipe made keeps naming it.
    """
    if not ObjectId.is_valid(item_id):
        raise fresh(INVALID_ID)
    found = await store.find({'_id': ObjectId(item_id), **owner_filter(user, OWNER)})
    if found is None:
        raise Refusal(Code.UNKNOWN_RECIPE, 'No recipe of yours has that id.')
    await store.delete(found['_id'])
    return RecipeDeleted(deleted=str(found['_id']))
