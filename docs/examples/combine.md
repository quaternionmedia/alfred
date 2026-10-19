# Combine media
All clips in the `clips` list will be combined to create the finished video. 

`start` sets when each clip begins, in seconds (default 0).

!!! abstract "Rendering order"
    Clips render in list order. Where clips overlap in time, the later one renders above the earlier, with any transparency applied.


``` json title="data.json" hl_lines="14"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "videos/moon.mp4",
        "duration": 5
      },
      {
        "type": "video",
        "name": "videos/train.mp4",
        "inpoint": 10,
        "duration": 5,
        "start": 5
      }
    ]
  }
}
```