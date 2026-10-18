# Template

A `Template` is a `Clip` whose picture is drawn rather than read from a file: text, or a colour. Its `name` is the template to draw, and its `data` what to draw with it.

``` json title="A template clip"
{
  "type": "template",
  "name": "textBox",
  "duration": 5,
  "data": {
    "text": "Drama is life with the dull bits cut out.",
    "color": "#f2aa4c"
  }
}
```

A template clip needs `data`, and is otherwise placed and timed like any [Clip](clip.md): `start`, `duration`, `inpoint` and `outpoint`, `fadeIn` and `fadeOut`, `opacity`, `position`, and `clipsize`, the size the template is drawn at, which is the frame unless it says otherwise.

!!! info
    `GET /templates` lists the templates this server offers, each with a `description`, the `parameters` its template takes, and whether it is `deprecated`.

## `name`
: `#!python str`
    
    The template to draw. This server offers:
    
    - `title`: a large title, with a box in `themecolor` revealed beside it
    - `textBox`: a block of text, with a box in `bg` behind it when one is given
    - `bullets` (deprecated): bullet points separated by `•`, one after another
    - `initial` (deprecated): the sentences of `text`, one after another
    - `makeColor`: the clip filled with one colour

    Any other name is refused: a render or a preview naming it is a 422, and `GET /preview/template/{name}` a 404. That includes `final`, which otto draws but this server does not offer: the address, website and phone it shows come from otto's own defaults, and nothing in `data` can change them.

## `data`
`data` holds the fields below. Any other key is dropped without an error, which is why some of the `parameters` `GET /templates` lists for a template, such as `opacity`, `fps` and `start`, cannot be set through it: the template keeps its own value.

``` python
class TemplateData:
    text: str
    color: str
    themecolor: str
    bg: str
    fontsize: float
    textsize: tuple
    font: str
    method: str = 'label'
    align: str
    position: tuple | str
    fxs: List[FX]
```

### `text`
: `#!python str`

    The words to draw. Every template but `makeColor` needs it: a preview without it is a 422, and a render fails, with the reason in its `error`.

### `color`
: `#!python str`

    The text's colour, as `#rrggbb`; white by default. For `makeColor`, the colour it fills the clip with.

### `themecolor`
: `#!python str`

    The colour of `title`'s box and of `bullets`' bar; yellow by default.

### `bg`
: `#!python str`

    A box of this colour behind the text, drawn at 40% opacity, for `title`, `textBox` and `initial`.

### `fontsize`
: `#!python float`

    The text's size. Without one, the text is sized to fill `textsize`.

### `textsize`
: `#!python tuple`

    The (width, height) of the box the text is set in; half the frame each way by default.

### `font`
: `#!python str`

    A font name as ImageMagick lists it on the server (`convert -list font`), such as `DejaVu-Sans`. A name it does not know is drawn in its default font, without an error.

### `method`
: `#!python str = 'label'`

    How the text is set: `label` keeps the lines it is given, and `caption` wraps it to the width of `textsize`.

### `align`
: `#!python str`

    For `textBox`, how its lines line up: `center` by default, or `west` or `east`.

### `position`
: `#!python tuple | str`

    Where the text sits in the template's frame, as a clip's [`position`](clip.md#position) is given.

### `fxs`
: `#!python List[FX]`

    Movements for `textBox`, `initial` and `bullets`, each `{"name": "bezier2", "data": {...}}`: the clip moves along a curve over its first second. See [Animate text](../examples/animation.md). Any other name is a 422.
