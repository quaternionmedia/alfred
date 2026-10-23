# Fade a clip

A clip fades in and out over one second unless it says otherwise: `fadeIn` and `fadeOut` set the length of each fade in seconds, and `0` turns a fade off. A clip's own fades are the only ones it gets -- templates add none of their own. (The editor sends `0` for both unless a fade was chosen, so its renders cut where the timeline cuts.)

## Fade In
: fade a clip in
``` json title="fade in" hl_lines="7"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "videos/moon.mp4",
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
        "name": "videos/moon.mp4",
        "fadeOut": 2
      }
    ]
  }
}
```
