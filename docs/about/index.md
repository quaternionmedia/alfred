# About

![The workspace with its Panels menu open: every panel, one marked closed, and Reset layout](../assets/screens/panels-menu.png)

*The workspace and its Panels menu, which brings back a closed panel or resets the layout.*

## [Concepts](concepts.md)
Alfred needs no video experience, but the [concepts of video editing](concepts.md) help.


## Design

Alfred has these components:

### website
: The editor in the browser: one page, worked in four stages.

    - **Source**: the projects, and the media and templates to put on a timeline
    - **Edit**: the timeline, a single track of clips played one after another,
      under a viewer that shows the clip at the playhead
    - **Render**: a render of the timeline at a chosen size, or, for a project
      built from a form, that form
    - **Deliver**: the renders as they progress, to download or deliver
    - **Captions**, beside them: typed, imported from a subtitle file, or
      transcribed, and drawn into renders

    On a wide screen the stages' panels are a workspace, rearranged by dragging
    and restored from the Panels menu; on a phone the editor shows one stage at
    a time. [Get started](../start.md) walks through all four.
### [API](../api/index.md)
: The server, as a backend service: accounts, projects, renders and captions,
  with otto drawing every preview and render.

### Models
The properties each model takes:

#### [Clip](clip.md)
#### [Template](template.md)
#### [Edl](edl.md)
#### [Project](project.md)
#### [Render](render.md)
