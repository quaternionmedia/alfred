# Working with Projects

The following is a complete example of a `Project` which makes a 10 second commercial. The desired `Edl` will include:

- a **BaseVideo**
    - duration: 10 seconds
- a **ProductImage**
    - starts at 5 seconds
    - resized to appear in the center right
- a **ProductName**
    - starts at 5 seconds
    - the text color can be changed
- a **Logo**
    - positioned at the bottom right corner

??? abstract "Layer order"
    All media items are rendered from first to last, meaning the final media listed will appear above all others.
## Project Data
``` json title="data.json"
--8<-- "docs/examples/project.json"
```

## ProjectAPI

=== "Create"
    To create a new project, issue a **POST** request.
    ``` bash title="Create new project"
    curl -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      https://alfred.quaternion.media/project
    ```

      A successful request returns the object, with it's `id` number.

    ``` json title="response"
    {"_id":"61db4127e2ab4bf1fd587ddc","logic":{...}...}
    ```
=== "Read All"
    To read a list of all projects, issue a **GET** request.
    ``` bash title="Get all projects"
    curl -H "Authorization: Bearer $TOKEN" \
      https://alfred.quaternion.media/project
    ```
=== "Read One"
    To read a Project, issue a **GET** request with the id of the project to read.
    ``` bash title="Get one project"
    curl -H "Authorization: Bearer $TOKEN" \
      https://alfred.quaternion.media/project/$PROJECT_ID
    ```
=== "Update"
    To update a Project, issue a **PUT** request with the id of the project to update.
    ``` bash title="Update project"
    curl -X PUT \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      https://alfred.quaternion.media/project
    ```
=== "Delete"
    To delete a Project, issue a **DELETE** request with the id of the project to delete.
    ``` bash title="Update project"
    curl -X PUT \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      https://alfred.quaternion.media/project/$PROJECT_ID
    ```
