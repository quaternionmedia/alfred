"""Who owns a record, and who may reach it: one rule for projects and renders.

A project names its owner in `owner` and a render in `username`, and both hold
the same thing: the owner key of the account that created it. This module is
the only place that knows what that key is, and what follows from it:

- `owner_key(user)` -- what a record stores to say `user` owns it;
- `owner_filter(user, field)` -- the query that restricts a collection to the
  records `user` may reach, given the field that collection keeps its owner in;
- `may_access(owner, user)` -- whether `user` may reach one record.

The rule behind all three: an account reaches what it owns, and a superuser
reaches everything, including records stored before ownership existed. Those
have no owner, so they match nobody else's key and are superuser-only by
construction rather than by a separate rule someone could forget.

Each collection used to carry its own copy of that rule -- `visible_to` beside
the projects, `can_access` and a list filter beside the renders -- and two
copies are two places for "may I see it" to disagree.

**The key is the account's email**, because that is what both collections have
always stored. It makes an email change an ownership change: the account keeps
its id and loses everything recorded against its old address. So while the key
is the email, an account's email cannot change (`changes_owner_key`; `PATCH
/users/me` answers 422). docs/ownership.md describes moving the key to the user
id, which lifts that restriction.
"""

# The account attribute an owner key is read from.
KEY_FIELD = 'email'


def owner_key(user) -> str:
    """What a record stores to say `user` owns it: today, the email."""
    return getattr(user, KEY_FIELD)


def sees_everything(user) -> bool:
    """Whether ownership does not restrict `user`: a superuser.

    `is_superuser` alone. The admin routes also ask for `is_verified`; why the
    two differ, and why that is not yet settled, is in docs/ownership.md.
    """
    return bool(getattr(user, 'is_superuser', False))


def owner_filter(user, field) -> dict:
    """The query restricting a collection to the records `user` may reach.

    `field` is where the collection keeps its owner key: `owner` for projects,
    `username` for renders. Empty -- everything -- for a superuser.
    """
    if sees_everything(user):
        return {}
    return {field: owner_key(user)}


def may_access(owner, user) -> bool:
    """Whether `user` may reach a record whose owner key is `owner`.

    The same rule as `owner_filter`, for a record already in hand. One with no
    owner is a superuser's alone: nobody else can be shown to own it, and
    guessing would hand one account another's work.
    """
    if sees_everything(user):
        return True
    return owner is not None and owner == owner_key(user)


def changes_owner_key(user, changes) -> bool:
    """Whether applying `changes` to `user` would change its owner key.

    `changes` maps account fields to new values, as an account update does.
    Sending the address the account already has is not a change.
    """
    return KEY_FIELD in changes and changes[KEY_FIELD] != owner_key(user)
