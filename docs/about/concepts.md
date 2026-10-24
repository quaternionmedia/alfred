# Concepts

## Timeline
A `Timeline` represents how to make a video.

Most video editors show `Clips` as blocks, left to right in time, each as long as its duration.

### Single Track Video Editing
A `Timeline` that plays one clip at a time.

It is a list of clips, in any order. Each clip plays for its `duration`, and the next starts where it ends, so the video lasts the sum of its clips' `duration`s.

### Multitrack Video Editing
A `Timeline` where several videos play at once, as layering needs.

It is also a list of clips, each rendered on its own "track", so videos stack on top of each other. With transparency, that allows any compositing.

## [Clip](clip.md)
A `Clip` is a single, continuous section of a video, referenced in a `Timeline`, of one of four types: `video`, `image`, `audio` or `template`.

These set its timing:

### `start`
: Where the clip begins in the finished video, in seconds. Default: `0`

### `inpoint`
: The start time for playing this video, in seconds. Default: `0`

### `outpoint`
: The end time for playing this video, in seconds. Optional.

### `duration`
: The length in seconds to play this video, when it has no `outpoint`. Default: `5`

??? abstract "Timing math"
    With an `outpoint`, a clip plays from its `inpoint` to its `outpoint`, for `outpoint - inpoint` seconds, and its `duration` is not read. Without one, it plays for `duration` seconds from its `inpoint`.
    
    The editor sends both, with `duration` equal to `outpoint - inpoint`, and a `start` for every clip: clips are layered by their own timing, not played one after another.

[Clip](clip.md) has every field.

## [Template](template.md)
A `Template` is a predefined `Clip` generator that renders custom text and graphics into video.

Each template takes parameters such as `text`, `font`, `fontsize`, `color`, `position` and `fxs`.

Templates are transparent by default, so they stack into more complex compositions.

## [EDL](edl.md)
An `EDL`, or **E**dit **D**ecision **L**ist, is a list of `Clips` combined into one video.

It is the data of the final video: every step from the source material (`video`, `photo`, `audio`, `templates`, etc.) to the finished product.

A `Timeline` can show any `EDL`.

## [Project](project.md)
A `Project` is a saved piece of work: its name, its timeline as an `EDL`, its captions, and the size it last rendered at and where it was last delivered. Choosing one in the editor brings all of it back.

A project can also be built from data: it holds `logic` to build the end product and `fields` that describe the data it needs. The `fields` are rendered as a `Form` to enter data into, on the editor's Render stage. The data is applied to the `logic`, which generates the `EDL` to render into a finished video.

## [Render](render.md)
A `Render` finalizes a video into a single file that any capable player can play.

Rendering is computationally expensive and usually needs powerful hardware. Alfred renders on the server you run, in its render worker, so any device with a browser can edit video.
