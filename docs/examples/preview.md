# Preview frame
Preview one frame of an `Edl` without rendering the full video

!!! note "Preview time"
    Preview time at `t` seconds is a required query parameter.

## Request
=== "Edl"
    ``` json title="data.json"
    {
      "edl": {
        "clips": [
          { 
            "type" : "template",
            "name" : "title",
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

Returns a signed URL for the rendered frame. It works without a session -- an
`<img src>` can use it as it is -- for the one frame it names, until its `exp`
(`ALFRED_MEDIA_URL_TTL`, 15 minutes by default). Frames are kept for
`ALFRED_FRAME_TTL` seconds, an hour by default.

```
/preview/frames/6f1c3e0b2a9d4c8e9b7a5d3f1e2c4b6a.jpg?exp=1760793600&sig=Zk8h…
```

``` bash title="Fetch the frame"
curl -o frame.jpg "https://alfred.quaternion.media$URL"
```
![Otto Template Preview](../../assets/20211203-221343.png){ align = right, loading = lazy }
