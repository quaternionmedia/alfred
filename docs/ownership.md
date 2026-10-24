# Ownership

Every project and render belongs to the account that created it. An account
reaches what it owns; a superuser reaches everything; a record stored before
ownership existed has no owner and is superuser-only. Anybody else gets a 404,
never a 403, so an id cannot be confirmed.

The rule lives in one module, `alfred/core/utils/ownership.py`, and both
collections go through it:

| | Stored in | Written by | Checked by |
|---|---|---|---|
| Projects | `project.owner` | `owner_key(user)` | `owner_filter(user, 'owner')` |
| Renders | `render.username` | `owner_key(user)` | `owner_filter(user, 'username')`, `may_access(render.username, user)` |

Seeds (`ALFRED_SEED_OWNER`, in development the dev user) and generated demos are
owned the same way.

## The key is the email, and that is a problem

`owner_key(user)` is the account's email, because that is what both
collections store. An email is a poor key:

- **It can change.** The account keeps its id and loses everything recorded
  against the old address, which then matches nobody. So for now nothing may
  change one: `PATCH /users/me` and a superuser's `PATCH /users/{id}` answer
  422 for a new `email` (`changes_owner_key`).
- **It can be reused.** Delete an account, and whoever next registers its
  address inherits its projects and renders.
- **It compares exactly.** `Alice@example.com` and `alice@example.com` are one
  login to fastapi-users, which looks addresses up case-insensitively, and two
  owners to MongoDB.

## Moving the key to the user id

The plan, not yet done:

1. **One write path, already in place.** Every record is stamped through
   `owner_key`, and every query scoped through `owner_filter` or `may_access`,
   so the key changes in one function, not at each call site.
2. **Backfill, idempotent.** For each user, rewrite `{owner: <email>}` on
   projects and `{username: <email>}` on renders to `str(user.id)`, matching
   the email exactly as stored (`update_many` per user and collection).
   Records whose address matches no account (a deleted user, a seed owner
   never registered) are listed, not guessed at, and left as they are. They
   match no id, so they become superuser-only, as an ownerless record is today.
   Give `./al` a command for it, `owners migrate`, with a dry run that prints
   the counts; run that, then the real thing.
3. **Switch the key.** `owner_key` returns `str(user.id)`. Ship it in the same
   release as the backfill, with the backfill run before the new api serves. A
   filter on ids finds nothing still keyed by email, so no fallback matching
   both is needed, and none should be added: it would keep the reuse problem
   alive.
4. **Lift the restriction.** `changes_owner_key` then reads the id, which
   never changes, so email changes pass with no further code.
5. **Name the seed owner by account.** `ALFRED_SEED_OWNER` and the dev user are
   addresses. Seeding has to resolve them to an id, creating the dev user first
   in development, which the auth bypass already knows how to do.
6. **Index the key.** `owner` and `username` are queried on every list; add an
   index on each while touching them.

What a client sees changes too: `project.owner` becomes an id. The SPA does not
read it. `website/e2e/auth.spec.js` compares it with the logged-in address, and
would compare it with `/users/me`'s `id` instead.

## Who counts as a superuser

`ownership.sees_everything(user)` is `is_superuser`, nothing more. The admin
router (`POST /invoice`) also requires `is_verified`, through
`current_active_superuser`. That looks like an inconsistency one line could
settle either way, and it is not quite:

- fastapi-users' own superuser routes (`GET`/`PATCH`/`DELETE /users/{id}`)
  require `is_superuser` alone, and `PATCH /users/{id}` may set
  `is_verified`. An unverified superuser can verify themselves in one request,
  so `is_verified` is no boundary for superusers anywhere today.
- Requiring it in `sees_everything` would silently hide every other account's
  projects, and every ownerless one, from an existing unverified superuser.
  Confirmation links reach anybody only where account mail is configured
  ([Auth](api/auth.md)).
- Dropping it from the admin router removes a check, however nominal.

It stays as it is, listed as an open decision. Either way, the visibility half
is one line in `sees_everything`. Making `/users/{id}` require verification too
means passing `requires_verification=True` to `get_users_router`, which would
also gate `/users/me`, and with it every unverified account's session.
