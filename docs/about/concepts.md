# Concepts

## Timeline
In video editing, a `Timeline` is a representation of how to create a video.

In most video editors, `Clips` are viewed as blocks, arranged from left to right in time, sized proportionate to their duration.

### Single Track Video Editing
A `Timeline` where only one clip can be played at a time. 

This is represented as a List of clips, which can be rearranged in any order. Each clip plays for its `duration`, and the next starts where it ends.

The total duration of the video is the sum of the `duration`s of it's clips.

### Multitrack Video Editing
A `Timeline` where multiple videos can play simultaneously. Necessary for layering videos.

A Multi-Track Timeline is also represented as a List of clips, where each video is rendered on a different "track", allowing multiple videos to be stacked on top of each other. When combined with transparencies, this allows for unlimited compositing opportunities for new videos.

## [Clip](clip.md)
A `Clip` is a single, continuous section of a video, referenced in a `Timeline`. 

Clips can be of four types: `video`, `image`, `audio` or `template`.

Timing of the clip is determined with the following variables:

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

For more details, refer to the [Clip](clip.md) documentation.

## [Template](template.md)
A `Template` is a predefined `Clip` generator, built to automate and simplify the process of rendering custom text and graphics in video. 

Each template accepts parameters such as `text`, `font`, `fontsize`, `color`, `position` and `fxs`. 

By default, templates are transparent, which means they can be stacked on top of each other to render more complex video compositions.

## [EDL](edl.md)
An `EDL`, or **E**dit **D**ecision **L**ist, is a list of `Clips` to be combined into a single video. 

The `EDL` is a data representation of the final video to be rendered. It describes all the steps necessary to take the source material (`video`, `photo`, `audio`, `templates`, etc.) and generate the desired final product.

Each `EDL` can be viewed in a `Timeline`.

## [Project](project.md)
A `Project` is a special data format, designed to automatically create templates from user data.

A Project contains `logic` to build the end product and `fields` that describe the data needed.

To create an `EDL`, the `fields` are rendered as a `Form`, where user data can be input. This data is applied to the `logic`, which generates the `EDL` to be rendered into a finished video.

## [Render](render.md)
A `Render` is the process of finalizing a video, so it can be easily played back as a single file by any machine capable of playing such videos.

Rendering is usually a computationally expensive operation, and generally requires powerful hardware to run. With Alfred, rendering is performed in the cloud, using a distributed system, which means any device can be a video editing platform!
