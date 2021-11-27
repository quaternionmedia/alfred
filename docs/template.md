# Template

A `Template` is a `Clip` designed to render text.

Each template can have unique properties, `fxs`, and values, according to each template schema.

!!! info
    Full list of values available from the API, at `/otto/templates`

Available properties:
``` python
class Template:
    name: str
    text: str
    data: dict = None
    color: str = None
    themecolor: str = None
    fontsize: float = None
    clipsize: tuple[int] = (1920,1080)
    textsize: tuple[int] = None
    font: str = 'Segoe-UI-Black'
    method: str = 'caption'
    duration: float = 5
    position: str = 'center'
    opacity: float = .4
    fps: float = 30
    bg: str = None
```
## `name`
: `#!python str`
    
    The name of the base template to use. Available options:
    
    - title
    - initial
    - bullets
    - final
    - textBox

    
## `text`
: `#!python str`

## `data`
: `#!python dict = None`

## `color`
: `#!python str = None`

## `themecolor`
: `#!python str = None`

## `fontsize`
: `#!python float = None`

## `clipsize`
: `#!python tuple[int] = (1920,1080)`

## `textsize`
: `#!python tuple[int] = None`

## `font`
: `#!python str = 'Segoe-UI-Black'`

## `method`
: `#!python str = 'caption'`

## `duration`
: `#!python float = 5`

## `position`
: `#!python str = 'center'`

## `opacity`
: `#!python float = .4`

## `fps`
: `#!python float = 30`

## `bg`
: `#!python str = None`
