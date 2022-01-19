# Combine media
All clips in the `clips` list will be combined to create the finished video. 

The `start` property defines the desired starting time for each clip (default 0).

!!! abstract "Rendering order"
    Clips are rendered in the order presented in the list. For clips that overlap in time, the last clip will be rendered above the earlier clips, including any transparencies applied.


``` json title="data.json" hl_lines="14"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "https://storage.googleapis.com/tower-bucket/moon.mp4",
        "duration": 5
      },
      {
        "type": "video",
        "name": "https://storage.googleapis.com/tower-bucket/train.mp4",
        "inpoint": 10,
        "duration": 5,
        "start": 5
      }
    ]
  }
}
```