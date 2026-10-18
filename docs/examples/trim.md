# Trim video
Selecting a portion of a video is as simple as defining an `inpoint`.

``` json title="data.json" hl_lines="7"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "videos/moon.mp4",
        "inpoint": 5,
        "duration": 5
      }
    ]
  }
}
```

The above Edl will result in a 5 second long video, skipping the first 5 seconds of the input.