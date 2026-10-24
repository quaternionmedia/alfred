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

This Edl makes a 5-second video that skips the input's first 5 seconds.