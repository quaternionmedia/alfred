# Project

A project is a saved piece of work: its timeline, its captions, and the size
it last rendered at. A project with `fields` and `logic` is made from a form
instead. Its fields draw a form on the Render stage, and its logic turns what
is typed there into clips, so one project makes the same kind of video again
and again with new words. [From a form](../journeys.md#from-a-form) walks it
in the editor.

## Fields

`fields` is a list. Each field names the component that draws it as its
`type`, gives that component its `attrs`, and gives a select its choices as
`children`.

| `type` | Draws | Its value |
|---|---|---|
| `Text` | a line of text | what is typed |
| `Textarea` | a box of text | what is typed |
| `Selector` | a choice of its `children` | the choice, a string; the first is chosen to start |
| `Color` | a colour picker | `#rrggbb` |
| `Image` | a media name or URL, with its picture | what is typed |

`attrs.name` is the name the logic reads the value by, and `attrs.text` is the
field's label. `attrs.defaultValue` fills a field once, as the form opens. A
`value` would be put back over what was typed at every redraw.

Every form also has **Resolution**, **Quality** and **Description**, after the
project's own fields.

## Logic

`logic` is [json-logic](https://jsonlogic.com/), evaluated in the browser over
the form's values, and over `width` and `height`, the frame chosen under
**Resolution**. It makes a list of clips, layered in order, each placed by its
own `start`; a clip with no `start` starts at 0. Besides json-logic's own
operations it has:

- `merge`, one list from the lists given;
- `eachKey`, an object whose every value is evaluated;
- `preserve`, a value taken as it stands;
- `floor` and `sqrt`.

## Announcement

The form project a new install starts with draws a background, a headline
that flies in from the right, and the details and the fine print from its
first second on. Its details layer:

``` json title="One layer of Announcement's logic"
{
  "eachKey": {
    "type": "template",
    "name": "textBox",
    "start": 1,
    "duration": {"-": [{"+": [{"var": "duration"}]}, 1]},
    "data": {
      "eachKey": {
        "text": {"var": "details"},
        "method": "caption",
        "fontsize": {"/": [{"sqrt": {"*": [{"var": "width"}, {"var": "height"}]}}, 32]},
        "align": {"if": [{"==": [{"var": "align"}, "left"]}, "west", "center"]}
      }
    }
  }
}
```

- `{"+": [...]}` reads the **Seconds** choice, a string, as a number.
- A font size taken from the square root of `width` times `height` keeps its
  proportion to the frame at every resolution.
- `method: caption` wraps the text to fit its box.

Every clip it makes is a template, so it needs no media; the whole project is
`ANNOUNCEMENT` in `alfred/seed.py`. [examples/project](../examples/project.md)
makes one through the API, with an image over a video.

Each project can also be rendered at several sizes.
