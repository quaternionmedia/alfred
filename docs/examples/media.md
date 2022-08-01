# Add media
All examples here can be previewed or rendered as a full video.
=== "Preview"
    Set the `t` variable to the desired preview time
    ``` bash title="Preview EDL"
    curl -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      https://alfred.quaternion.media/preview?t=1
    ```

=== "Render"
    ``` bash title="Render"
    curl -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @data.json \
      https://alfred.quaternion.media/render
    ```

## Video

``` json title="Video source"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "https://storage.googleapis.com/tower-bucket/moon.mp4",
        "duration": 10
      }
    ]
  }
}
```

## Images
``` json title="Image source"
{
  "edl": {
    "clips": [
      {
        "type": "image",
        "name": "https://storage.googleapis.com/tower-bucket/alfred/qm/LanguageArchive.jpg",
        "duration": 5
      }
    ]
  }
}
```
## Audio
``` json title="Audio source"
{
  "edl": {
    "clips": [
      {
        "type": "audio",
        "name": "https://storage.googleapis.com/tower-bucket/alfred/tala/talaaudio.mp3"
      }
    ]
  }
}
```
