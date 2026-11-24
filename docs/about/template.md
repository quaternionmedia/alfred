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

A template clip needs `data`, and is otherwise placed and timed like any [clip](https://github.com/quaternionmedia/otto/blob/51a1b0eb1d53d99f3ae55083406901ed1255ec40/docs/timeline.md#a-clip): `start`, `duration`, `inpoint` and `outpoint`, `fadeIn` and `fadeOut`, `opacity`, `position`, and `clipsize`, the size the template is drawn at (the frame, by default).

!!! info
    `GET /templates` lists the templates this server offers, each with its `name` (what a clip's `name` must be), a `label` for people to read (`Text box` for `textBox`), a `description`, the `parameters` its template takes, and whether it is `deprecated`.

## `name`
: `#!python str`
    
    The template to draw. This server offers:
    
    - `title`: a large title, with a box in `themecolor` revealed beside it
    - `textBox`: a block of text, with a box in `bg` behind it when one is given
    - `bullets` (deprecated): bullet points separated by `•`, one after another
    - `initial` (deprecated): the sentences of `text`, one after another
    - `makeColor`: the clip filled with one colour

    Any other name is refused: a 422 from a render or a preview, and a 404 from `GET /preview/template/{name}`. That includes `final`, which otto draws but this server does not offer: its address, website and phone come from otto's own defaults, and nothing in `data` changes them.

## `data`

`data` is otto's `TemplateData`: [otto's table](https://github.com/quaternionmedia/otto/blob/51a1b0eb1d53d99f3ae55083406901ed1255ec40/docs/timeline.md#template-data) has
each field, what it draws and its default, and [`fxs`](https://github.com/quaternionmedia/otto/blob/51a1b0eb1d53d99f3ae55083406901ed1255ec40/docs/timeline.md#fxs) the
movement. Any other key is dropped without an error, so some `parameters`
that `GET /templates` lists, such as `opacity`, `fps` and `start`, cannot be
set through it: the template keeps its own value. What this server adds:

- **`text`** is needed by every template but `makeColor`: without it, a
  preview is a 422, and a render fails with the reason in its `error`.
- **`font`** is a name as ImageMagick lists it on the server, such as
  `DejaVu-Sans`. [`GET /fonts`](../api/fonts.md) lists the families this
  server has. An unknown name is drawn in the default font, without an error.
- **`fxs`** naming anything but `bezier2` is a 422. See [Animate
  text](../examples/animation.md).

