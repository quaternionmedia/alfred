# Models

The following data structures define how Alfred creates videos from `Clips` through `Edl`s.


## Clip
A `Clip` is any single video, represented as a `json` dictionary.

```python
class Clip:
    duration: float = 5
    type: str
    name: str
    inpoint: float
    outpoint: float
    offset: float
    start: float
    position: tuple
    data: dict
    resize: [float, tuple]
    relative: bool = True
    fxs: dict
```

## Edl
An `Edl` (**E**dit **D**ecision **L**ist) is a list of `Clip`s needed to generate a rendered video. 
```python
class Edl(BaseModel):
    clips: List[Clip]
    duration: float = None
```
