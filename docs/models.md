# Models

The following data structures define how Alfred creates videos from `Clips` through `Edl`s.


## Clip
A `Clip` is any single video, represented as a `json` dictionary.

All fields are optional.

``` python
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
#### Properties
### **`duration`**
*float*

The total length of this clip, in seconds.

### **`type`**
*str*

Template type of clip. Possible values include:

- video
- audio
- title
- initial
- bullets
- final
- textBox


Each template can have unique properties, `fxs`, and values, according to each template schema.

Full list of values available from the API, at `/otto/templates`

### **`name`**
*str*

The name of this clip. For `type: video`, this is the url, or relative server path to the desired video.

### **`inpoint`**
*float*

The number of seconds from the beginning of clip to the desired start time of the video.

### **`outpoint`**
*float*

The number of seconds from the beginning of clip to the desired end time of the video.

### **`offset`**
*float*

Offset the start time of the video by `n` seconds.

A positive value behaves the same as `start`, delaying the start time by `n` seconds

A negative value behaves like a negative `inpoint`, and will trim from the beginning of clip by `n` seconds.

### **`start`**
*float*

The number of seconds to delay the start of the clip.

Positive values only.

### **`position`**
*tuple(float, float)*

`relative: True` *default* - Reposition the clip by `(x, y)` percent of the frame.

`relative: False` - Reposition the clip by `(x, y)` pixels

### **`relative`**
*bool = True*

Sets whether `position` acts as absolute position (pixel), or relative (percent).

### **`data`**
*dict*

Defines values to be rendered into the template. 

Specific to each template. For example:

``` json
{
  "type": "title", 
  "data": {
    "text": "Text to be rendered",
    "font": "font_name",
    "color": "#FF0000",
    "textsize": "50",
    "method": "caption",
    "duration": "5",
    "position": "center",
    "opacity": ".5",
  }
}
```

### **`resize`**
*[float, tuple]*

Scale the size of the clip.

- *float*: Scale the clip by `x, x`
- *tuple*: Resize the clip by `x, y`

### **`fxs`**
*List*

Apply a list of `fx` to a clip.

Available FX:

- boxReveal
- flyInAndGrow
- bezier2
- zoomFromCenter
- circleShrink
- boxShrink
- drawBoxOutline


## Edl
An `Edl` (**E**dit **D**ecision **L**ist) is a list of `Clip`s needed to render a finalized video. 
``` python
class Edl:
    clips: List[Clip]
    duration: float = None
```
### `clips`
*List[Clip]*

A list of clips to render into a finalized video.

**Note** `Clip`s are rendered in the order listed, as a multi-track timeline. If multiple clips overlap, the first clip will be rendered on the "bottom" of the video stack, and the last clip will be rendered above all others, with any transparencies applied. 

### duration
*float*

An optional duration (in seconds) to trim an `Edl` to a desired length.
