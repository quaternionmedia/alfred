# Skipping login in development

`ALFRED_DEV_SKIP_AUTH=1` serves every request as a fixed superuser and lets the
SPA skip its login screen. It exists so work on the editor does not require a
round trip through registration and JWT handling on every fresh database.

```sh
ALFRED_DEV_SKIP_AUTH=1 ./al dev
```

The stack prints a banner on every boot while it is on:

```
========================================================================
  AUTHENTICATION IS DISABLED (ALFRED_DEV_SKIP_AUTH)
  Every request is served as dev@example.com, a superuser.
  Local development only. Never expose this process.
========================================================================
```

## What it actually does

Every route guarded by `current_active_user` or `current_active_superuser`
resolves to one account instead of authenticating the caller. The bypass is
all-or-nothing: the dev account is a verified superuser, so the admin routes
open too. Anything finer grained is auth work, which is the next phase.

The account is a **real, persisted user**, not a stand-in object. Routes do
more than gate on the dependency -- `render.py` attributes records to
`user.id` -- so a fake would make those paths behave differently under the
bypass than under real auth, which would defeat the purpose of developing
against it.

`/users/me` is shadowed by a dev-only route registered ahead of the
fastapi-users one. Swapping the dependency is not enough to cover it:
`get_users_router` builds its own dependency internally from the
authenticator, so it is a different callable, and `dependency_overrides` keys
on identity. Without the shadow the SPA's probe would 401 and the login screen
would come back while every other endpoint stayed open.

## What keeps it out of production

1. **Explicit opt-in.** Off unless the variable is `1`, `true`, `yes` or `on`.
   `ALFRED_DEV_SKIP_AUTH=0` and `=false` are off -- deliberately, because
   `bool(environ.get(...))` treats both as on, and those are the two spellings
   someone writes when they mean to disable it.
2. **Refuses to combine with `ALFRED_PRODUCTION`.** Setting both raises at
   import and the process does not start. Ignoring the flag would be the more
   common choice and is the wrong one: the operator who set it believes it
   took effect, and the process comes up looking healthy either way.
3. **No production passthrough.** The variable is wired only in `dev.yml`.
   `production.yml` does not mention it, so a production stack has no
   environment variable to read even if one were set on the host.
4. **The dev account cannot be logged into.** It stores `!dev-no-login` where
   a password hash belongs. fastapi-users verifies a candidate against that
   hash, and no input hashes to it, so the account is unusable as a way in
   once the flag is off again -- which matters, because it is a superuser and
   it persists.

Guard 2 is the load-bearing one, and it is worth knowing its limit:
`ALFRED_PRODUCTION` is set by `production.yml`, so a deployment that does not
use that file gets no refusal. The banner is the backstop, and it is why the
banner is unmissable rather than a log line.

## What it does not change

The e2e suite runs against a normal stack. `test_e2e.yml` has no passthrough
for the variable, and several specs assert that an anonymous caller is refused
-- they would fail with the bypass on, correctly.

## Known defect in this area

`/users/me` does not return a usable `id`, with or without the bypass. Under
real authentication it serialises as `{}`; under the bypass, as `null`. The
underlying user has a real ObjectId in both cases, so this is a `UserRead`
serialisation problem rather than an auth one. It predates the bypass and is
recorded here because this is where it was found.
