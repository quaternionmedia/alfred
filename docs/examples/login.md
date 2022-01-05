# Login
Tokens can be acquired with a `POST` request, with a username (email address) and password as form data.

??? abstract "Register for new account"
    If you have not already done so, register for a new account by visiting [https://alfred.quaternion.media/login](https://alfred.quaternion.media/login)
    
    Registering can also be performed as an API request:
    
    ``` bash title="Register"
    curl -X POST \
      -d '{"email":"your@email","password":"yourpassword","first_name":"yourname"}' \
      https://alfred.quaternion.media/auth/register
    ```
    
    This returns an object with information about the user.
    ``` json
    {"id":"801d4a32-ad97-4dfe-9c20-eb98b6640ee2","email":"your@email","is_active":true,"is_superuser":false,"is_verified":false,"first_name":"yourname"}
    ```
    
    After successful email validation, you can request a login token to use with protected API routes.

## Request token
``` bash
curl -X POST \
  -F "username=user@email" \
  -F "password=yourpassword" \
  https://alfred.quaternion.media/auth/jwt/login
```
## Results
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


!!! abstract "`curl | jq`"
    The following is a bash one-liner to create a local `$TOKEN` variable using `curl` and `jq`.
    ``` bash
    export TOKEN=$(curl -X POST \
      -F "username=your@email"
      -F "password=yourpassword" \
      https://alfred.quaternion.media/auth/jwt/login | jq -r '.access_token')
    ```
