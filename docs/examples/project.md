# Save Project

To store a project for future use, use the `/project` API.

## Create
=== "curl"
    ``` bash title="Create new project"
    curl -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      https://stage.alfred.quaternion.media/project
    ```

=== "data.json"
    ``` json
    {
      "logic": {
        {
          "type": "video",
          "name": "https://storage.googleapis.com/tower-bucket/moon.mp4"
        },
        {
          "start": 5,
          "type": "image",
          "name": {
            "var": "ProductImage"
          }
        },
        {
          {
            "start": 5,
            "type": "template",
            "name": "textBox",
            "data": {
              "text": {
                "var": "ProductName"
              }
            }
          }
        }
      },
      "fields": [
        { "type": "Text",
            "attrs": {
              "name": "ProductImage",
              "text": "Link to product image",
            }
        },
        { "type": "Textarea",
            "attrs": {
              "name": "ProductName",
              "text": "Product Name",
            }
        },
      ]
    }
    ```

A successful request returns the object, with it's `id` number.

``` json title="response"
{"_id":"61db4127e2ab4bf1fd587ddc","logic":{...}...}
```

## Read

## Update
To update a Project, issue a **POST** request with the id of the project to update.
``` bash title="Update project"
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @data.json \
  https://stage.alfred.quaternion.media/project/$PROJECT_ID
```

## Delete
