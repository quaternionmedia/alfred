# Fade a clip

By default, clips have no fade time. Adding a `fadeIn` or `fadeOut` parameter will create a smooth transition for the specified duration in seconds.

## Fade In
: fade a clip in
``` json title="fade in" hl_lines="7"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "https://storage.googleapis.com/tower-bucket/moon.mp4",
        "fadeIn": 2
      }
    ]
  }
}
```

## fade Out
: fade a clip out
``` json title="fade out" hl_lines="7"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "https://storage.googleapis.com/tower-bucket/moon.mp4",
        "fadeOut": 2
      }
    ]
  }
}
```
