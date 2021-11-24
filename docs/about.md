# About
> "Drama is life with all the dull bits cut out."
>
> ~ Alfred Hitchcock

## Origin
Alfred began as a simple, serverless video client, designed to manipulate a list of edits in a browser, to be rendered into a finished video by a powerful backend.

Since then, the project has grown to include a suite of video and editing tools, including rendering, previewing, and task automation that would otherwise be done manually.

## Design

Alfred is split into several components:

- `website`: The browser based tools to create and edit videos, including:
    - "simple" single-track video editor
    - "advanced" multi-track video editor
    - template rendering forms
    - preview frame of video
    - check renders status and download
- `API`: The video rendering components, available as a backend service.

## Concepts
### Timeline
In video editing, a `Timeline` is a graphical representation of how to create a video. Clips are arranged as blocks from left to right in time, sized proportionate to their duration.

### Clip
A `Clip` is a single, continuous section of a video, referenced in a `Timeline`. 

Clips have optional properties such as:

#### type
A type of clip, either `video`, `audio`, or `template`

#### name
The canonical name for this type of clip.

`type: video`: The url location of this video.

`type: audio`: The url location of this audio.

`type: template`: The name of the template to render

#### inpoint
The start point for playing this video, in seconds.

#### outpoint
The end point for playing this video, in seconds.

#### duration
The length in seconds to play this video.


### Single-Track Video Editing
A `Timeline` where only one clip can be played at a time. 

This is represented as a List of clips, which can be rearranged in any order. Each clip will play until the `duration` is reached, or if not specified, the end of the video clip.

### Multi-Track Video Editing
A `Timeline` where multiple videos can play simultaneously. Necessary for layering videos.

A Multi-Track Timeline is also represented as a List of clips, but each video is rendered on a different "track", allowing multiple videos to be stacked on top of each other. When combined with transparencies, this allows for unlimited compositing opportunities for new videos.
