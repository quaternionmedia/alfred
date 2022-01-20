# Generate text

This example posts a single `Template` clip that generates a `text` in large title format.

!!! note "Preview time"
    Preview time at `t` seconds is a required query parameter.

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
      https://alfred.quaternion.media/preview?t=1
    ```

## Results

Returns a local url to the rendered file

```
data/20211203-221343.png
```
![Otto Template Preview](../../assets/20211203-221343.png){ align = right, loading = lazy }

## Properties
Change the Properties of the text by passing `data` parameters.

``` json title="animation" hl_lines="9-10"
{
  "edl": {
    "clips": [
      {
        "type": "template",
        "name": "textBox",
        "data": {
          "text": "asdf",
          "font": "Open-Sans",
          "color": "#FF00FF"
        }
      }
    ]
  }
}
```

## Result

![Animation preview](../../assets/20220111-071708.png){ align = right, loading = lazy }

For a full list of available properties, see [about/template](../../about/template).
