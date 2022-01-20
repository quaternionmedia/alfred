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

## Create
=== "Request"
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

## Read

## Update
To update a Project, issue a **PUT** request with the id of the project to update.
``` bash title="Update project"
curl -X PUT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @data.json \
  https://alfred.quaternion.media/project/$PROJECT_ID
```

## Delete
