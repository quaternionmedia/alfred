# Preview frame
Preview one frame of an `Edl` without rendering the full video

!!! note "Preview time"
    The time to preview, `t` in seconds, is a required query parameter. The route is `/preview/`, slash included: without it the request never reaches the preview, and is answered 405.

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
      "https://alfred.quaternion.media/preview/?t=1"
    ```

The body is a render request, so `width` and `height` beside `edl` set the frame's size, 1920 by 1080 by default. The `Edl` is checked as a render's is, and a clip the server will not render is a 422 that names it.

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

The frame is a JPEG, over black where nothing is drawn:

![The title template at t=1](../assets/preview-title.jpg){ loading = lazy }
