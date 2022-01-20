# Adjust clip
## Resize
Resizing an image is as simple as passing the resize scale factor.

- Values larger than 1 will enlarge the clip
- Values less than 1 will shrink the clip

``` json title="data.json"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "https://storage.googleapis.com/tower-bucket/moon.mp4",
        "resize": 2.5
      }
    ]
  }
}
```

## Position
Reposition the clip

- Positive `x` values move the image **right**
- Negative `x` values move the image **left**
- Positive `y` values move the image **down**
- Negative `y` values move the image **up**
=== "Absolute"
    Move the clip by `[x, y]` pixels from the top left.
    ``` json title="data.json"
    {
      "edl": {
        "clips": [
          {
            "type": "video",
            "name": "https://storage.googleapis.com/tower-bucket/moon.mp4",
            "position": [
              "center",
              "top"
            ]
          }
        ]
      }
    }
    ```
=== "Relative"
    Move the clip by `[x, y]`, where `1` represents the width or height of the frame.
    
    The below example places this video at the center, top of the frame.
    ``` json title="data.json"
    {
      "edl": {
        "clips": [
          {
            "type": "video",
            "name": "https://storage.googleapis.com/tower-bucket/moon.mp4",
            "relative": true,
            "position": [
              0.5,
              1
            ]
          }
        ]
      }
    }
    ```
=== "Text"
    Place the clip at `[x, y]` of one of the following coordinates:

    | axis | values |
    | ----- | ----- |
    | x | `left`, `center`, `right` |
    | y | `top`, `center`, `bottom` |
        
    ``` json title="data.json"
    {
      "edl": {
        "clips": [
          {
            "type": "video",
            "name": "https://storage.googleapis.com/tower-bucket/moon.mp4",
            "position": [
              "center",
              "top"
            ]
          }
        ]
      }
    }
    ```
