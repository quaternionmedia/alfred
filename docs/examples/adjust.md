# Adjust clip
## Resize
A video or image is first fitted inside the frame, keeping its proportions, and centred. Resizing scales it from there by the factor given.

- Values larger than 1 will enlarge the clip
- Values less than 1 will shrink the clip

``` json title="data.json"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "videos/moon.mp4",
        "resize": 2.5
      }
    ]
  }
}
```

## Position
Reposition the clip. A position of numbers places the clip's top left corner, from the frame's top left:

- Larger `x` values move the clip **right**
- Smaller `x` values, down to negative ones, move the clip **left**
- Larger `y` values move the clip **down**
- Smaller `y` values, down to negative ones, move the clip **up**

Each example below shrinks the clip to half the frame first, so that where it sits shows.
=== "Absolute"
    With `"relative": false`, move the clip by `[x, y]` pixels from the top left. This places it 100 pixels from the left and 50 from the top.
    ``` json title="data.json"
    {
      "edl": {
        "clips": [
          {
            "type": "video",
            "name": "videos/moon.mp4",
            "resize": 0.5,
            "relative": false,
            "position": [
              100,
              50
            ]
          }
        ]
      }
    }
    ```
=== "Relative"
    Move the clip by `[x, y]`, where `1` represents the width or height of the frame. Positions are relative unless the clip says `"relative": false`.
    
    The below example places this half-size video at the center, top of the frame: its left edge a quarter of the way across.
    ``` json title="data.json"
    {
      "edl": {
        "clips": [
          {
            "type": "video",
            "name": "videos/moon.mp4",
            "resize": 0.5,
            "relative": true,
            "position": [
              0.25,
              0
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
        
    This places it exactly as the relative example above does.
    ``` json title="data.json"
    {
      "edl": {
        "clips": [
          {
            "type": "video",
            "name": "videos/moon.mp4",
            "resize": 0.5,
            "position": [
              "center",
              "top"
            ]
          }
        ]
      }
    }
    ```
