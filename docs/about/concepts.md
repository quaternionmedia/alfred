# What makes a video

A video in alfred is a project's timeline, rendered. Four things make it up.
The timeline's format is otto's, and [otto's timeline
page](https://github.com/quaternionmedia/otto/blob/51a1b0eb1d53d99f3ae55083406901ed1255ec40/docs/timeline.md)
has every field of it; where it and this page differ, otto's decides. This page
says what alfred adds.

## The timeline

A timeline is an `Edl`, an edit decision list: `clips`, and an optional
`duration`. Each clip is a `video`, `image`, `audio` or `template`, placed on
the output by its own timing (`start`, `inpoint`, `outpoint` and `duration`),
and where clips overlap a later one is drawn over an earlier one. otto's page
has [the clips](https://github.com/quaternionmedia/otto/blob/51a1b0eb1d53d99f3ae55083406901ed1255ec40/docs/timeline.md#a-clip)
and [the timing rules](https://github.com/quaternionmedia/otto/blob/51a1b0eb1d53d99f3ae55083406901ed1255ec40/docs/timeline.md#timing).

The editor lays its clips end to end on one track. It sends each clip a
`start`, its place on the timeline, and both an `outpoint` and a `duration`
equal to `outpoint - inpoint`, so a render places the clips as the screen
shows them.

What alfred adds to otto's rules:

- **A media clip's `name` is in the library**: `videos/<file>`, as `GET
  /videos` lists it, or an `http(s)` URL on a host `ALFRED_REMOTE_MEDIA_HOSTS`
  allows ([Configuration](../configuration.md#media-renders-and-delivery)).
  Absolute paths, `..` and other schemes are refused.
- **A template clip names a template this server offers**, which `GET
  /templates` lists ([Template](template.md)).
- **A clip alfred will not touch is refused when the request arrives**: an
  unknown type, media outside the library, a template not offered. The 422
  names the clip by its place, counted from 1, before anything is stored or
  queued. A clip otto cannot build, such as an `outpoint` before its
  `inpoint`, is a 422 from a preview and fails a render, with the reason in
  its `error`.

## [Template](template.md)

A clip whose picture is drawn rather than read from a file: a title, a block
of text, a colour. Templates are transparent around what they draw, so they
stack over video.

## [Project](project.md)

A saved piece of work: its name, its timeline, its captions, and the size it
last rendered at and where it was last delivered. Choosing one in the editor
brings all of it back. A project can also be built from data: `logic` makes
the timeline from what a form, described by its `fields`, collects on the
Render stage.

## [Render](render.md)

One request to make a video of a timeline, at a size and a quality, which the
server's render worker draws with otto into one file any player can play. So
any device with a browser can edit video.
