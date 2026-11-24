# Working with Projects

The following is a complete example of a `Project` which makes a 10 second commercial. The desired `Edl` will include a:

- **BaseVideo**
    - duration: 10 seconds
- **ProductImage**
    - starts at 5 seconds
    - resized to appear in the center right
- **ProductName**
    - starts at 5 seconds
    - the text color can be changed
- **Logo**
    - positioned at the bottom right corner

??? abstract "Layer order"
    Clips render from first to last, so the last one listed appears above all others.

The image fields are media names like any clip's: `videos/<file>` from the server's library, or a URL on a host `ALFRED_REMOTE_MEDIA_HOSTS` lists. See the [usage notes](index.md).

## Project Data
``` json title="data.json"
--8<-- "docs/examples/project.json"
```

## ProjectAPI

=== "Create"
    **POST** a new project.
    ``` bash title="Create new project"
    curl -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      http://127.0.0.1:8000/project
    ```

    It answers the project as stored, with the `_id` the server gave it.

    ``` json title="response"
    {"_id":"61db4127e2ab4bf1fd587ddc","logic":{...}...}
    ```
=== "Read All"
    **GET** your projects; a superuser gets every project.
    ``` bash title="Get all projects"
    curl -H "Authorization: Bearer $TOKEN" \
      http://127.0.0.1:8000/project
    ```
=== "Read One"
    **GET** one project by its id.
    ``` bash title="Get one project"
    curl -H "Authorization: Bearer $TOKEN" \
      http://127.0.0.1:8000/project/$PROJECT_ID
    ```
=== "Update"
    **PUT** a project by its id.
    ``` bash title="Update project"
    curl -X PUT \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      http://127.0.0.1:8000/project/$PROJECT_ID
    ```
    The body replaces the project: a field it leaves out is emptied, though the owner and captions are kept. `PUT /project/$PROJECT_ID/timeline` writes the timeline alone, and `PUT /project/$PROJECT_ID/settings` the render settings and destination alone.
=== "Delete"
    **DELETE** a project by its id.
    ``` bash title="Delete project"
    curl -X DELETE \
      -H "Authorization: Bearer $TOKEN" \
      http://127.0.0.1:8000/project/$PROJECT_ID
    ```
    This answers the project as it was.
