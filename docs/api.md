# API
Sometimes, it is more convenient to interact directly with the API, bypassing the browser based client entirely. This is especially true when building a larger application. The following is a guide to interacting with the native functions and generating videos directly from a data object.

This is an advanced topic, and requires some tool to make requests to the server. The following examples are provided using `curl`, but any requests library will have comparable features.

For the full API reference (including interactive request generator), visit [alfred.quaternion.media/api](https://alfred.quaternion.media/api)

## auth
Authentication is performed with JWT token headers. All requests must provide a valid token to access any routes.

### login
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

## otto

## preview

## render

### `GET /render`

### `POST /render`

## issues
Report any issues with renders with the `/report/{render}` endpoint.
