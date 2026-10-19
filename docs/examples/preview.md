# Preview frame
Preview one frame of an `Edl` without rendering the full video

!!! note "Preview time"
    `t`, the time to preview in seconds, is a required query parameter. The route is `/preview/`, slash included: without the slash, the request never reaches the preview and is answered 405.

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

The body is a render request, so `width` and `height` beside `edl` set the frame's size, 1920 by 1080 by default. The `Edl` is checked as a render's is: a clip the server will not render is a 422 that names it.

## Results

It answers a signed URL for the rendered frame. The URL works without a
session (an `<img src>` can use it as it is) for the one frame it names, until
its `exp` (`ALFRED_MEDIA_URL_TTL`, 15 minutes by default). Frames are kept for
`ALFRED_FRAME_TTL` seconds, an hour by default.

```
/preview/frames/6f1c3e0b2a9d4c8e9b7a5d3f1e2c4b6a.jpg?exp=1760793600&sig=Zk8h…
```

``` bash title="Fetch the frame"
curl -o frame.jpg "https://alfred.quaternion.media$URL"
```

The frame is a JPEG, over black where nothing is drawn:

![The title template at t=1](../assets/preview-title.jpg){ loading = lazy }

## When the server is busy

The server draws a few previews at once for everyone together,
`ALFRED_PREVIEW_CONCURRENCY` (four by default), counting `POST /preview/` and
`GET /preview/template/{name}` alike. Past that, a preview waits its turn for
up to `ALFRED_PREVIEW_WAIT` seconds (ten by default), then is answered `503`
with a `Retry-After` header giving the seconds to wait before asking again:

```
HTTP/1.1 503 Service Unavailable
Retry-After: 2

{"detail": "The server is already drawing as many previews as it will (4 at once); ask again in 2 seconds.", "code": "previews_busy"}
```

Wait that long, then ask once more, as the editor's viewer does. `GET /health`
says how the turns are going: `previews: {running, waiting, limit}`.
