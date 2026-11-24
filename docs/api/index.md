# API

Everything the editor does goes through alfred's HTTP API, and a program can
call it the same way: make a project, preview a frame, render a timeline and
fetch the video, without a browser. The examples use `curl`; any request
library works.

- **[Concepts](../about/index.md)**: what a request carries, a timeline of
  clips, a template, a project and a render, and which part of each is otto's.
- **[Examples](../examples/index.md)**: log in, add media, preview a frame,
  render, trim, combine, fade and animate, each a request you can send to the
  dev stack, checked by the browser suite.
- **Routes**: [auth](auth.md), [otto's previews and templates](otto.md),
  [fonts](fonts.md), [renders](render.md), and the [refusals](errors.md), each
  with the `code` a program can switch on.

!!! note
    Every route, with an interactive request generator, is at `/api` on any
    alfred: <http://127.0.0.1:1732/api> on the dev stack, and
    [alfred.quaternion.media/api](https://alfred.quaternion.media/api).
