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

Both pages work without a session; the login screen's **forgot password**
asks for the first. Asking answers `202` whether or not the address has an
account.

Account mail needs the mail settings the invoice mail uses -- `EMAIL_SERVER`,
`EMAIL_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD` -- and `ALFRED_PUBLIC_URL`,
the address people reach the app at (`https://alfred.example.com`). The link is
built on that setting and never on the request's Host header, which whoever
asks for a reset controls. Without all of them nothing is mailed:

- in development the token is printed in the api's log, which is how a
  development stack finishes a reset;
- under `ALFRED_PRODUCTION` the log records that a token was issued, and why
  nothing was mailed, and never the token itself.

The development login (`ALFRED_DEV_USER_EMAIL`) is never sent a reset token,
and cannot be given a password; see [Skipping login in development](../dev-auth.md).
