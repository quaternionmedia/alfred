# Alfred

<img src="assets/screens/edit.png" alt="The editor on a wide screen: a workspace of docked panels" width="60%"> <img src="assets/screens/phone-edit.png" alt="The editor on a phone: the Edit stage over the viewer" width="17%"> <img src="assets/screens/phone-render.png" alt="The editor on a phone: the Render stage over the viewer" width="17%">

*The editor on a wide screen, as a workspace of panels, and on a phone, one stage at a time: Edit, then Render.*

Alfred is a browser video editor for quick editing from anywhere, mobile
devices included. The browser edits the timeline; every preview and render is
made by an Alfred server you run yourself, with cloud storage optional.

The editor is one page, worked in four stages named on the rail along its top:

1. **Source**: choose a project, and the media and templates for its timeline.
2. **Edit**: arrange, trim and cut the clips, title them, and cut the video by
   deleting words from its transcript.
3. **Render**: choose the output's size, and have the server make the video.
4. **Deliver**: follow the render, then download it or send it on.

## Where to go

- **[Journeys](start.md)**: from a clone to the editor answering, then [what
  you came to do](journeys.md), from a first video to captions, a phone and an
  account, and [one video made with the whole family](guide.md). The editor's
  own **How?** links open them.
- **[Reference](captions.md)**: [captions](captions.md), [editing by
  text](editing-by-text.md), the [editing tools](tools.md), and every
  [setting](configuration.md) the server reads.
- **[Develop](develop.md)**: the questions a new developer asks, each settled
  by one command, then the test loop, the family loop and how the stacks are
  built.
- **[API](api/index.md)**: what a timeline, a project and a render are, and
  videos made without the editor, with `curl`.
- **[History](retrospective-0.3.0.md)**: what earlier rounds taught, and the
  rules they left.

## How it is built

A small control plane, `alfred`, owns accounts, projects, renders, captions
and their orchestration, and hands the media work to the rest of the family,
each with docs of its own:

| | Its part | Its docs |
|---|---|---|
| **otto** | draws every preview frame and render, and mixes the timeline's sound | [otto's docs](https://github.com/quaternionmedia/otto/tree/main/docs) |
| **vox** | drives an audio engine over HTTP, by a contract | [vox's README](https://github.com/quaternionmedia/vox#readme) |
| **joe** | the audio engine: hears the sound and times each word | [joe's docs](https://github.com/quaternionmedia/joe/tree/main/docs) |
| **qmcp** | QM's tool server: an assistant drives alfred through its `alfred_*` tools | [qmcp](https://github.com/quaternionmedia/qmcp) |

Where a page here says what an engine does, the engine's own docs decide.
[The family dev loop](family.md) runs them together.

!!! quote "Alfred Hitchcock"
    Drama is life with all the dull bits cut out.

## Links
App: [alfred.quaternion.media](https://alfred.quaternion.media)

Documentation: [alfred.quaternion.media/docs/](https://alfred.quaternion.media/docs/)

API Reference: [alfred.quaternion.media/api](https://alfred.quaternion.media/api)

Source code: [github.com/quaternionmedia/alfred](https://github.com/quaternionmedia/alfred)
