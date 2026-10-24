# Auth
Authentication is performed with JWT token headers. All requests must provide a valid token to access any protected routes.

See [examples/login](../examples/login.md)

## Password resets and address confirmation

`POST /auth/forgot-password` and `POST /auth/request-verify-token` issue a
single-use token, valid for an hour. With account mail configured, the server
mails it to the account's address as a link into the app:

- `<ALFRED_PUBLIC_URL>/#!/account/reset?token=...` opens a page that takes the
  new password and sends it to `POST /auth/reset-password`;
- `<ALFRED_PUBLIC_URL>/#!/account/verify?token=...` confirms the address
  through `POST /auth/verify` as it opens.

Both pages work without a session; the login screen's **forgot password** asks
for the first. Asking answers `202` whether or not the address has an account.

Account mail needs the mail settings the invoice mail uses (`EMAIL_SERVER`,
`EMAIL_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`) and `ALFRED_PUBLIC_URL`, the
address people reach the app at (`https://alfred.example.com`). The link is
built on that setting, never on the request's Host header, which whoever asks
for a reset controls. Without all of them, nothing is mailed:

- in development, the api's log prints the token, which is how a development
  stack finishes a reset;
- under `ALFRED_PRODUCTION`, the log records that a token was issued and why
  nothing was mailed, never the token itself.

The development login (`ALFRED_DEV_USER_EMAIL`) is never sent a reset token,
and cannot be given a password; see [Skipping login in development](../dev-auth.md).

## Password hashing

Passwords are hashed with bcrypt, slow on purpose: about 0.3 s a hash or a
check. fastapi-users 10.4 does that work inside its coroutines, on the api's
one event loop, where nothing else (not a preview, not `/healthz`) would be
answered while a login is checked. So alfred carries its own copies of the
library's five methods that hash or check a password (`authenticate`,
`create`, `forgot_password`, `reset_password` and `_update`), identical but
for hashing in the thread pool, in `alfred/core/utils/passwords.py`.

Guards keep the copied security code from drifting quietly from the original:

- **It refuses to run against any other release.** The copies name the
  fastapi-users release they were checked against, 10.4.2, and a fingerprint
  of each original's source. On import, a different release or a changed
  method stops the api from starting, naming the method that changed and what
  to re-check.
- **Tests hold each copy to its original**
  (`tests/unit/test_password_hashing.py`): the same lookups, writes, hashes,
  checks and answers, case by case. That includes the hash run for an unknown
  address, which keeps its refusal as slow as a wrong password, and the upgrade
  of an outdated hash at login. Other tests show `/healthz` answering while a
  login is checked, and `tests/unit/test_blocking_calls.py` fails if a
  coroutine hashes directly.
- **The api says so as it starts**, in one line beginning `Password hashing:`.

So upgrading fastapi-users starts with that module: read each replaced method
in the new release, carry over what changed, and update the release and the
fingerprints it records.
