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
more than gate on the dependency -- renders and projects are attributed to the
caller's email (`render.username`, `project.owner`) and filtered by it -- so a
fake would make those paths behave differently under the bypass than under
real auth, which would defeat the purpose of developing against it.

## What the dev account sees

Records belong to the account that created them, and other accounts get a 404
for them. Being a superuser, the dev account sees **every** project and render,
not only its own -- remember that when something looks shared in development
that would not be for a normal account. It also owns what development creates
for it:

- **Seed projects** are written as the dev user's at startup, and by `./al seed`
  and `./al reseed`. `ALFRED_SEED_OWNER` names a different owner; under
  `ALFRED_PRODUCTION` seeds have no owner unless it is set, which makes them
  visible to superusers only.
- **Demo projects** from `POST /demo/project` are one per account, so the dev
  user gets its own.

Registration is open in development and closed under `ALFRED_PRODUCTION`;
`ALFRED_ALLOW_REGISTRATION` overrides either default. To see the app as a
normal account would, turn the bypass off and register one -- at any address
but the dev account's, which is refused (see guard 5).

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
   `production.yml` names it only to say it is withheld, and does not pass
   it, so a production stack has no environment variable to read even if one
   were set on the host. `tests/unit/test_stack_settings.py` holds that.
4. **Loopback by default.** `dev.yml` publishes the api on 127.0.0.1, so with
   the bypass on, the superuser is reachable from this machine only.
   `ALFRED_BIND=0.0.0.0` opens it to the network (to try the editor on a phone,
   say), and `./al dev` warns when that is combined with the bypass.
5. **The dev account cannot be logged into, or claimed.** It stores
   `!dev-no-login` where a password hash belongs, so no password matches it,
   and a login is refused like a wrong one. That matters, because it is a
   superuser and it persists once the flag is off again -- so nothing may
   change it either: its address cannot be registered (the bypass makes the
   account on first use, and until then whoever registered the address owned
   the dev seeds), no password can be set on it by a reset or by a
   superuser's `PATCH /users/{id}`, and no reset token is issued for it. The
   rules live on `UserManager`, which every one of those routes goes through.

Guard 2 is the load-bearing one, and it is worth knowing its limit:
`ALFRED_PRODUCTION` is set by `production.yml`, so a deployment that does not
use that file gets no refusal. The banner is the backstop, and it is why the
banner is unmissable rather than a log line.

## What it does not change

The e2e suite runs against a normal stack. `test_e2e.yml` has no passthrough
for the variable, and several specs assert that an anonymous caller is refused
-- they would fail with the bypass on, correctly.

## A defect found here, since fixed

`/users/me` used not to return a usable `id`: `{}` under real authentication
and `null` under the bypass, a `UserRead` serialisation problem that predated
the bypass. It returns the id as a string in both cases now;
`tests/unit/test_user_serialisation.py` pins it.
