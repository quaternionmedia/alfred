# auth
Authentication is performed with JWT token headers. All requests must provide a valid token to access any protected routes.

## login
Tokens can be acquired with a `POST` request, with a username (email address) and password as form data.

``` bash
curl -X POST \
  -F "username=user@ema.il" \
  -F "password=yourpassword" \
  https://alfred.quaternion.media/auth/jwt/login
```
returns:
``` json
{
  "access_token" : "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiZjBmZDg2YTMtMjIwZi00NGQ4LWEwYWMtZjNlMTllYzRjYTE3IiwiYXVkIjpbImZhc3RhcGktdXNlcnM6YXV0aCJdLCJleHAiOjE2Mzc4MDY0MTN9.0eHCVBDbjUkWUY4kwK-VVO-OOVUO6lAfMZUo9XclYlM",
  "token_type" : "bearer"
}
```

Requests can now be made by providing this token in the headers.
``` bash
export TOKEN=y0UrAPiT0k3N...
curl \
  -H "Authorization: bearer $TOKEN" \
  https://alfred.quaternion.media/protected
```
