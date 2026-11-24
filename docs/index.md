# Alfred

<img src="assets/screens/edit.png" alt="The editor on a wide screen: a workspace of docked panels" width="60%"> <img src="assets/screens/phone-edit.png" alt="The editor on a phone: the Edit stage over the viewer" width="17%"> <img src="assets/screens/phone-render.png" alt="The editor on a phone: the Render stage over the viewer" width="17%">

*The editor on a wide screen, as a workspace of panels, and on a phone, one stage at a time: Edit, then Render.*

Alfred is a browser video editor for quick editing from anywhere, mobile
devices included. The browser edits the timeline; every preview and render is
made by an Alfred server you run yourself, with cloud storage optional.

The editor is one page, worked in four stages named on the rail along its top:

1. **Source**: choose a project, and the media and templates for its timeline.
2. **Edit**: arrange, trim and cut the clips on the timeline, and set a title's
   text, length and colours.
3. **Render**: choose the output's size and queue a render, which the server
   makes.
4. **Deliver**: follow the render until it is finished, then download it or send
   it to a destination.

Beside them, **Captions** are typed, imported from a subtitle file, or
transcribed from the timeline's sound, and drawn into renders. On a screen
1024 pixels wide or more, the panels are a workspace you can rearrange, with a
Panels menu to bring back a closed one; narrower, as on a phone, the editor
shows one stage at a time above the viewer and the timeline.

## Start here

1. [Get started](start.md): run Alfred on your own machine and make a first
   video, from Source to Deliver.
2. [Cookbook](cookbook.md): the journeys through the editor, step by step,
   generated from the browser tests that check them.
3. [Captions](captions.md) and [Configuration](configuration.md): captions in
   the editor and through the API, and every setting the server reads.
4. [Concepts](about/index.md): clips, templates, timelines, projects and
   renders. [Examples](examples/index.md) and the [API](api/index.md) make
   videos without the editor, with `curl`.

## How it is built

A small control plane, `alfred`, owns accounts, projects, renders, captions
and their orchestration, and hands the media work to two engines: otto draws
every preview frame and render and mixes the timeline's sound, and vox drives
an audio engine such as joe over HTTP, which transcribes captions from that
sound. [The family dev loop](family.md) runs them together.

!!! quote "Alfred Hitchcock"
    Drama is life with all the dull bits cut out.

## Links
App: [alfred.quaternion.media](https://alfred.quaternion.media)

Documentation: [alfred.quaternion.media/docs/](https://alfred.quaternion.media/docs/)

API Reference: [alfred.quaternion.media/api](https://alfred.quaternion.media/api)

Source code: [github.com/quaternionmedia/alfred](https://github.com/quaternionmedia/alfred)
