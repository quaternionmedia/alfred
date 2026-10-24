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

    The clips to render into a finalized video.

    !!! info "Clip Rendering Order"
        `Clip`s render in the order listed, as a multi-track timeline: the first at the "**bottom**" of the video stack, the last above all others, with any transparency applied.

### `duration`
: `#!python float`

    Optional: the length, in seconds, to trim the `Edl` to.
