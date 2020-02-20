# alfred
> *"Drama is life with all the dull bits cut out."*
>
>  ~ Alfred Hitchcock

Alfred is a video editor that works even without a server, designed for quick editing from anywhere, including mobile devices!

Demo at [alfred.quaternion.media](https://alfred.quaternion.media)

### dev
`./alfred dev`

then open http://localhost:8000

If the docker images need to be rebuilt: `./alfred dev --build`

If package.json has changed, you might need to: `./alfred install` or `npm i`

### demo
To download the demo media (into `videos/`):

`./alfred demo`

Then you can render the `demo.csv` project locally.

### production
With a [traefik](https://containo.us/traefik/) instance running:
`./alfred prod`


### design
Alfred is a single track video editor, which represents a rearrangeable series of `Clips`, stacked end to end in time.

- `Clip` - a section of time of a media file. Clips have:
  * `filename`: name (url) of media
  * `inpoint`:  start time
  * `outpoint`: end time
  * `duration`: (`outpoint` - `inpoint`)
  * `description`: text


- `Edl` - **E**dit **D**ecision **L**ist. An ordered list of `Clips`
  - An `Edl` represents the entire state of the desired finished video.


- `Timeline` - a visual representation of an `Edl`
  - `Clips` are displayed as blocks sized proportionately to their durations.
  - `Clips` can be resized as the length of the source media allows.
  - `Clips` can be rearranged by dragging and dropping.
  - When possible, adjacent `Clips` wrap to the next line in the browser depending on available space in the window.
  - the `Timeline` can be scaled to any size needed with the `Scale` bar.


- `Monitor` - an html `<video>` monitor
  - This follows the current time of the active `Clip` in the `Timeline`


- `Project` - an editable table of values of the `Edl`
  - This is an identical representation of the `Timeline`, but in text format.


- `Projects` - a list of available `Edl`s to load


- `Bin` - a list of available media to use in the `Timeline`


- `Tools` - a panel of selectable tools


- `Slider` - a slideable (and throwable) input
  - `Scale` bar
  - `Timeline` position slider
