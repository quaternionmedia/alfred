# Add media
All examples here can be previewed or rendered as a full video. A clip's `name` is a file in the server's media library, as `GET /videos` lists it; the [usage notes](index.md) say where the files come from, and what a URL needs instead.

=== "Preview"
    Set `t` to the time to preview, in seconds. The route is `/preview/`, slash included: without it the request never reaches the preview, and is answered 405.
    ``` bash title="Preview EDL"
    curl -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      "https://alfred.quaternion.media/preview/?t=1"
    ```
    This answers a signed URL for the frame; see [Preview frame](preview.md).

=== "Render"
    ``` bash title="Render"
    curl -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      https://alfred.quaternion.media/render
    ```
    This answers the render's id; see [Render video](render.md).

## Video
A video clip plays its file from the start for `duration` seconds, 5 unless it says otherwise, scaled to fit inside the frame with its proportions kept, and centred. Its sound is mixed into the render's.

``` json title="Video source"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "videos/moon.mp4",
        "duration": 10
      }
    ]
  }
}
```

## Images
An image is shown for `duration` seconds, fitted and centred as a video is. `videos/poster.jpg` stands for an image of yours in the library: `GET /media` lists each file with its `kind`.
``` json title="Image source"
{
  "edl": {
    "clips": [
      {
        "type": "image",
        "name": "videos/poster.jpg",
        "duration": 5
      }
    ]
  }
}
```
## Audio
An audio clip is heard and not seen: it is mixed into the render's sound for `duration` seconds, 5 unless it says otherwise. A timeline of audio clips alone renders over black. `videos/soundtrack.mp3` stands for an audio file of yours in the library.
``` json title="Audio source"
{
  "edl": {
    "clips": [
      {
        "type": "audio",
        "name": "videos/soundtrack.mp3"
      }
    ]
  }
}
```
