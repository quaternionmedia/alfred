# Render
The following are the available properties available to `Render`

``` python title="Render"
class Render:
    edl: Edl
    name: str
    project: str
    project_id: id
    description: str
    duration: float
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    quality: str
    bitrate: List
    ffmpeg_params: List[str]
    
```

For a full working example, see [examples/render](../../examples/render)
