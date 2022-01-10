# Working with Projects

To store a project for future use, use the `/project` API.

## Create
=== "curl"
    ``` bash title="Create new project"
    curl -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      https://alfred.quaternion.media/project
    ```

=== "data.json"
    ``` json
    {
      "name":  "product commercial",
      "logic":  {
        "merge":  [
          {"eachKey":  {
            "type": "video",
            "name": "https://storage.googleapis.com/tower-bucket/moon.mp4"
          }},
          {"eachKey": 
          {
            "start": 5,
            "type": "image",
            "name": {
              "var": "ProductImage"
            }
          }},
          {"eachKey":  {
            "start": 5,
            "type": "template",
            "name": "textBox",
            "data": {"eachKey": {
              "text": {
                "var": "ProductName"
                }
              }}
            }
          }
        ]
      },
      "fields": [
        { "type": "Text",
          "attrs": {
              "name": "ProductImage",
              "text": "Link to product image"
            }
        },
        { "type": "Textarea",
            "attrs": {
              "name": "ProductName",
              "text": "Product Name"
            }
        }
      ]
    }
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
