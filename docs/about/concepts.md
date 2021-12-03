# Concepts

## Design

Alfred is split into several components:

### website
: The browser based tools to create and edit videos, including:
    
    - "simple" single-track video editor
    - "advanced" multi-track video editor
    - template rendering forms
    - preview frame of video
    - check renders status and download
### [API](../api)
: The video rendering components, available as a backend service.


## Timeline
In video editing, a `Timeline` is a graphical representation of how to create a video. Clips are arranged as blocks from left to right in time, sized proportionate to their duration.

### Single Track Video Editing
A `Timeline` where only one clip can be played at a time. 

This is represented as a List of clips, which can be rearranged in any order. Each clip will play until the `duration` is reached, or if not specified, the end of the video clip.

The total duration of the video is the sum of the `duration`s of it's clips.

### Multitrack Video Editing
A `Timeline` where multiple videos can play simultaneously. Necessary for layering videos.

A Multi-Track Timeline is also represented as a List of clips, where each video is rendered on a different "track", allowing multiple videos to be stacked on top of each other. When combined with transparencies, this allows for unlimited compositing opportunities for new videos.

## [Clip](../clip)
A `Clip` is a single, continuous section of a video, referenced in a `Timeline`. 

Clips can be of several types, including `video`, `audio`, `template`, or `edl`.

Timing of the clip is determined with the following variables:

### `inpoint`
: The start time for playing this video, in seconds. Default: `0`

### `outpoint`
: The end time for playing this video, in seconds. Default: `video.duration`

### `duration`
: The length in seconds to play this video. Default: `video.duration`

??? abstract "Timing math"
    The `duration` should always equal to the `outpoint - inpoint`.
    
    Any of these may be omitted, for example: 
    
    A `Clip` with `outpoint: 10` and `duration: 5` implies `inpoint: 5`

## [Template](../template)
A `Template` is a predefined `Clip` generator, built to automate and simplify the process of rendering custom text and graphics in video. 

Each template accepts parameters such as `text`, `font`, `fontsize`, `fontcolor`, `position`, `fxs`, and many others. 

By default, templates are transparent, which means they can be stacked on top of each other to render more complex video compositions.

## [EDL](../edl)
An `EDL`, or **E**dit **D**ecision **L**ist, is a list of `Clips` to be combined into a single video. 

The `EDL` is a data representation of the final video to be rendered. It describes all the steps necessary to take the source material (`video`, `photo`, `audio`, `templates`, etc.) and generate the desired final product.

Each `EDL` can be viewed in a `Timeline`, or imported as a `Clip` into a different `Timeline`.

## Project
A `Project` is a special data format, designed to automatically create templates from user data.

A Project contains `logic` to build the end product and `fields` that describe the data needed.

To create an `EDL`, the `fields` are rendered as a `Form`, where user data can be input. This data is applied to the `logic`, which generates the `EDL` to be rendered into a finished video.
