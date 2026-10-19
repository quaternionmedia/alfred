# Skipping login in development

`ALFRED_DEV_SKIP_AUTH=1` serves every request as a fixed superuser and lets the
SPA skip its login screen, so work on the editor needs no round trip through
registration and JWT handling on every fresh database.

```sh
ALFRED_DEV_SKIP_AUTH=1 ./al dev
```

While it is on, the stack prints a banner on every boot:

```
========================================================================
  AUTHENTICATION IS DISABLED (ALFRED_DEV_SKIP_AUTH)
  Every request is served as dev@example.com, a superuser.
  Local development only. Never expose this process.
========================================================================
```

## What it does

Every route guarded by `current_active_user` or `current_active_superuser`
resolves to one account instead of authenticating the caller. The bypass is
all-or-nothing: the dev account is a verified superuser, so the admin routes
open too. Anything finer grained is auth work, the next phase.

The account is a **real, persisted user**, not a stand-in. Routes attribute
renders and projects to the caller's email (`render.username`,
`project.owner`) and filter by it, so a fake would behave differently under the
bypass than under real auth, defeating the point of developing against it.

`/users/me` is shadowed by a dev-only route registered ahead of fastapi-users'
own. Overriding the dependency does not cover it: `get_users_router` builds its
own dependency from the authenticator, a different callable, and
`dependency_overrides` keys on identity. Without the shadow, the SPA's probe
would 401 and bring back the login screen while every other endpoint stayed
open. `/users/me` returns the id as a string, under real auth and the bypass
alike; `tests/unit/test_user_serialisation.py` pins it.

## What the dev account sees

Records belong to the account that created them, and other accounts get a 404
for them ([Ownership](ownership.md)). As a superuser, the dev account sees
**every** project and render, not only its own: something that looks shared in
development may not be for a normal account. It also owns what development
creates for it:

- **Seed projects**, written at startup and by `./al seed` and `./al reseed`.
  `ALFRED_SEED_OWNER` names another owner; [Configuration](configuration.md)
  says who owns them under `ALFRED_PRODUCTION`.
- **Demo projects** from `POST /demo/project`, one per account, so the dev user
  gets its own.

To see the app as a normal account does, turn the bypass off and register one
(registration is open in development) at any address but the dev account's,
which is refused (guard 5).

## What keeps it out of production

1. **Explicit opt-in.** Off unless the variable is `1`, `true`, `yes` or `on`.
   `ALFRED_DEV_SKIP_AUTH=0` and `=false` are off on purpose:
   `bool(environ.get(...))` treats both as on, and they are what someone writes
   to disable it.
2. **Refuses to combine with `ALFRED_PRODUCTION`.** With both set, import
   raises and the process does not start. Ignoring the flag instead would leave
   the operator believing it took effect, with a process that looks healthy
   either way.
3. **No production passthrough.** Only `dev.yml` wires the variable.
   `production.yml` names it only to say it is withheld, so a production stack
   has no variable to read even if the host sets one.
   `tests/unit/test_stack_settings.py` holds that.
4. **Loopback by default.** `dev.yml` publishes the api on 127.0.0.1, so with
   the bypass on, the superuser is reachable from this machine only.
   `ALFRED_BIND=0.0.0.0` opens it to the network (to try the editor on a phone,
   say), and `./al dev` warns when that meets the bypass.
5. **The dev account cannot be logged into, or claimed.** It stores
   `!dev-no-login` where a password hash belongs, so no password matches it,
   and a login is refused like a wrong one. It is a superuser that persists
   once the flag is off, so nothing may change it either:
   - its address cannot be registered (the bypass makes the account on first
     use; until then, whoever registered the address would own the dev seeds);
   - no reset, and no superuser's `PATCH /users/{id}`, can set its password;
   - no reset token is issued for it.

   The rules live on `UserManager`, which every one of those routes goes
   through.

Guard 2 is the load-bearing one, and it has a limit: `production.yml` sets
`ALFRED_PRODUCTION`, so a deployment that does not use that file gets no
refusal. The banner is the backstop, which is why it is unmissable rather than
a log line.

## What it does not change

The e2e suite runs against a normal stack. `test_e2e.yml` has no passthrough
for the variable, and several specs assert that an anonymous caller is refused;
with the bypass on, they would fail, correctly.
