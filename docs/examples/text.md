# Generate text

This example posts a single `template` clip that draws `text` in the large `title` format.

!!! note "Preview time"
    `t`, in seconds, is required, and so is the slash in `/preview/`; see [Preview frame](preview.md).

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

It answers a signed URL for the frame, which works without a session until its `exp`.

```
/preview/frames/6f1c3e0b2a9d4c8e9b7a5d3f1e2c4b6a.jpg?exp=1760793600&sig=Zk8h…
```
![The title template at t=1](../assets/preview-title.jpg){ loading = lazy }

## Properties
Set the text's properties in `data`:

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

`font` is a font name as ImageMagick lists it (`convert -list font` on the server); an unknown name is drawn in the default font, without an error.

## Result

![The textBox template at t=1, in DejaVu Sans and #FF00FF](../assets/preview-textbox.jpg){ loading = lazy }

[about/template](../about/template.md) lists every property.
