# Render video
Render an `Edl` with a single video and download the result when it is finished.

See [about/render](../about/render.md) for every field a render request takes, and [about/edl](../about/edl.md) for the timeline itself.

## Request
=== "Edl"
    ``` json title="data.json"
    {
      "edl": {
        "clips": [
          {
            "type": "video",
            "name": "videos/moon.mp4"
          }
        ]
      },
      "width": 1920,
      "height": 1080,
      "fps": 30,
      "quality": "standard"
    }
    ```

=== "Request"
    ``` bash title="Render Video"
    curl -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d @data.json \
      https://alfred.quaternion.media/render
    ```

!!! note "Render settings go in the body"
    `width`, `height`, `fps` and `quality` are fields of the request body, beside `edl`, and query parameters are ignored: `/render?width=1280` renders at the default 1920x1080.

    `width` and `height` are 16 to 7680 pixels, `fps` 1 to 120 frames a second, and `quality` one of `draft`, `standard` (the default) or `high`. The server encodes with that preset: a request carrying `bitrate` or `ffmpeg_params` is refused with a 422, as is one with a setting out of range.

## Result
If the render was queued, this returns its `id`, as a JSON string.
``` bash title="RenderId"
"61a43a5d6f511ec4ba99ac63"
```

A request the server will not render is answered 422 before anything is stored or queued, with a `detail` that says why: media outside the library, a template the server does not offer, a setting out of range. A problem with one clip names it, counting from 1.

## Check status
``` bash title="Render status"
curl -H "Authorization: Bearer $TOKEN" \
  https://alfred.quaternion.media/render/$RENDER_ID/status
```
``` json title="Status"
{
  "id": "61a43a5d6f511ec4ba99ac63",
  "state": "rendered",
  "status": "RENDERED",
  "progress": 100.0,
  "filename": "61a43a5d6f511ec4ba99ac63.mp4",
  "destination": null,
  "error": null,
  "download_url": "/render/61a43a5d6f511ec4ba99ac63/download?exp=1760793600&sig=Zk8h…"
}
```
`state` is `queued`, `rendering`, `rendered` or `failed`, and `error` says why a failed render failed. `progress` is a percentage. `download_url` is null until the video is finished.

`GET /render` lists your renders, newest first, each with its `download_url`.

## Download
`download_url` is a signed link to the finished video. It needs no `Authorization` header, so a browser can use it as a `<video src>` or a download link, until its `exp`.
``` bash title="Download the render"
curl -o render.mp4 "https://alfred.quaternion.media$DOWNLOAD_URL"
```

With the token, `GET /render/$RENDER_ID/download` serves the same file. Either way the video arrives as an attachment named for its project, description and size, and a `Range` header gets part of it, so a player can seek.

!!! note "Link expiration"
    Links are signed when a status or a listing is asked for, and work for `ALFRED_MEDIA_URL_TTL` seconds: 15 minutes by default, rounded up to the next whole minute. Ask again for a fresh one.

## Deliver
``` bash title="Deliver the render"
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  "https://alfred.quaternion.media/render/$RENDER_ID/deliver?destination=local"
```
This sends a finished render to a destination and answers where it went, `{"destination": "local", "location": "/render/61a43a5d6f511ec4ba99ac63/download"}`. `GET /destinations` lists the destinations the server offers. Without `destination`, a render goes where it was last sent, or else to `local`. It is a 409 until the render has finished.

## Multiple formats
Multiple outputs can be rendered from the same `Edl`, each from a request of its own. For example:

- HD / SD sizes
- Horizontal / Vertical aspect ratios
- Frame rates
- Qualities (`draft` for a quick look, `high` for the final cut)

Each request is queued as its own render, and answers its own `id` to follow and download it by. Every render is an MP4.
