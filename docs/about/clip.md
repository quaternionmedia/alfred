# Clip

: A `Clip` is one element of an `Edl`: a piece of media, or a template, placed on the timeline. It is a `json` object.

``` python
class Clip:
    type: str
    name: str
    duration: float = 5
    start: float
    inpoint: float
    outpoint: float
    offset: float          # deprecated
    fadeIn: float = 1
    fadeOut: float = 1
    opacity: float
    position: tuple | str
    relative: bool = True
    resize: float | tuple
    clipsize: tuple
    data: TemplateData
```

## Properties
Every field but `type` and `name` is optional.

A clip the server will not touch (an unknown type, media outside the library, a template it does not offer) is refused with a 422 when the request arrives. One the engine cannot build, such as an `outpoint` before its `inpoint`, is a 422 from a preview and fails a render, with the reason in its `error`. Either way the message names the clip, counting from 1.

### `type`
: `#!python str`

    What the clip is: `video`, `image`, `audio` or `template`.

### `name`
: `#!python str`

    For a template, which one; see [template](template.md). For media, the file: `videos/<file>`, as `GET /videos` lists it, or an `http(s)` URL on a host the server's `ALFRED_REMOTE_MEDIA_HOSTS` allows.

### `duration`
: `#!python float = 5`

    How long the clip plays, in seconds, when it has no `outpoint`. More than 0.

### `start`
: `#!python float`

    Where the clip begins in the output, in seconds. Absent is 0, and negative is refused.

### `inpoint`
: `#!python float`

    Where playback begins in the clip's source, in seconds. Absent is 0, and negative is refused.

### `outpoint`
: `#!python float`

    Where playback ends in the source, in seconds, after the `inpoint`. With one, the clip plays for `outpoint - inpoint` seconds, and `duration` is not read.

### `offset`
: `#!python float`

    Deprecated: use `start` or `inpoint`. A positive offset is added to `start`, and a negative one to `inpoint`.

### `fadeIn`, `fadeOut`
: `#!python float = 1`

    Seconds of fade at the clip's start and at its end, of its picture and of its sound; `0` or null for none. See [Fade a clip](../examples/fade.md).

### `opacity`
: `#!python float`

    From 0, invisible, to 1, opaque.

### `position`
: `#!python tuple | str`

    Where the clip sits in the frame: one of `center`, `left`, `right`, `top` or `bottom`, or an `(x, y)` pair. In a pair, a number places the clip's top left corner along its axis, and a word (`left`, `center` or `right` for x; `top`, `center` or `bottom` for y) lines the clip up with that side of the frame, or centres it. A video or image clip without a position is centred. See [Adjust clip](../examples/adjust.md).

### `relative`
: `#!python bool = True`

    Whether `position`'s numbers are fractions of the frame, so `(0.5, 0)` is halfway across at the top, or pixels from its top left corner (`false`).

### `resize`
: `#!python float | tuple`

    Scales the clip after it is fitted into the frame, or into its `clipsize`: by a factor, or to `(width, height)` pixels. Positive.

### `clipsize`
: `#!python tuple`

    For a template, the size it is drawn at; for media, the box it is fitted into, keeping its proportions. The frame by default.

### `data`
: `#!python TemplateData`

    What a template clip draws; every template clip needs it. See [template](template.md).

    ??? example "Sample JSON Template"
          ``` json
          {
            "type": "template",
            "name": "title",
            "duration": 5,
            "data": {
              "text": "Text to be rendered",
              "font": "DejaVu-Sans",
              "color": "#FF0000",
              "position": "center"
            }
          }
          ```

Movement belongs to templates, as their `data.fxs`. A clip has no `fxs` of its own, and one sent with a clip is dropped.
