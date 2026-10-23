# Generate text

This example posts a single `template` clip that draws `text` in the large `title` format.

!!! note "Preview time"
    The time to preview, `t` in seconds, is a required query parameter, and the route is `/preview/`, slash included.

=== "Edl"
    ``` json title="data.json" hl_lines="8"
    {
      "edl": {
        "clips": [
          {
            "type": "template",
            "name": "title",
            "data": {
              "text": "asdf"
            }
          }
        ]
      }
    }
    ```

=== "Request"
    ``` bash title="Preview template at t=1"
    curl -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d @data.json \
      "https://alfred.quaternion.media/preview/?t=1"
    ```

## Results

Returns a signed URL for the frame, which works without a session until its `exp`; see [Preview frame](preview.md).

```
/preview/frames/6f1c3e0b2a9d4c8e9b7a5d3f1e2c4b6a.jpg?exp=1760793600&sig=Zk8h…
```
![The title template at t=1](../assets/preview-title.jpg){ loading = lazy }

## Properties
Change the Properties of the text by passing `data` parameters.

``` json title="data.json" hl_lines="9-10"
{
  "edl": {
    "clips": [
      {
        "type": "template",
        "name": "textBox",
        "data": {
          "text": "asdf",
          "font": "DejaVu-Sans",
          "color": "#FF00FF"
        }
      }
    ]
  }
}
```

`font` is a font name as ImageMagick lists it (`convert -list font` on the server); a name it does not know is drawn in its default font instead, without an error.

## Result

![The textBox template at t=1, in DejaVu Sans and #FF00FF](../assets/preview-textbox.jpg){ loading = lazy }

For a full list of available properties, see [about/template](../about/template.md).
