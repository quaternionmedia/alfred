# Edl
An `Edl` (**E**dit **D**ecision **L**ist) is a list of `Clip`s needed to render a finalized video. 
``` python
class Edl:
    clips: List[Clip]
    duration: float = None
```
Available properties:
### `clips`
: `#!python List[Clip]`

    A list of clips to render into a finalized video.

    ??? info "Clip Rendering Order"
        `Clip`s are rendered in the order listed, as a multi-track timeline. If multiple clips overlap, the first clip will be rendered on the "**bottom**" of the video stack, and the last clip will be rendered above all others, with any transparencies applied. 

### `duration`
: `#!python float`

    An optional duration (in seconds) to trim an `Edl` to a desired length.
