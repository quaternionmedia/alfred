# Login
Tokens can be acquired with a `POST` request, with a username (email address) and password as form data.

!!! abstract "Register for new account"
    Register at [https://alfred.quaternion.media/login](https://alfred.quaternion.media/login), or with an API request:
    
    ``` bash title="Register"
    curl -X POST \
      -H "Content-Type: application/json" \
      -d '{"email":"your@email","password":"yourpassword","first_name":"yourname"}' \
      https://alfred.quaternion.media/auth/register
    ```
    
    It answers the new user:
    ``` json
    {"id":"61db4127e2ab4bf1fd587ddc","email":"your@email","is_active":true,"is_superuser":false,"is_verified":false,"first_name":"yourname","birthdate":null,"address":null}
    ```
    
    You can ask for a token straight away: logging in does not wait for the address to be confirmed.

    A production server takes registrations only when `ALFRED_ALLOW_REGISTRATION` opens it to them. A closed one answers 403 with the reason, and an administrator hands out its accounts.

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

Send the token in the headers of each request:
``` bash
export TOKEN=y0UrAPiT0k3N...
curl \
  -H "Authorization: bearer $TOKEN" \
  https://alfred.quaternion.media/users/me
```

A token works for an hour. `POST /auth/jwt/refresh`, sent with a token that still works, answers a fresh one in the same shape; an expired token has to log in again.


!!! abstract "`curl | jq`"
    A bash one-liner that sets `$TOKEN` with `curl` and `jq`:
    ``` bash
    export TOKEN=$(curl -X POST \
      -F "username=your@email" \
      -F "password=yourpassword" \
      https://alfred.quaternion.media/auth/jwt/login | jq -r '.access_token')
    ```
