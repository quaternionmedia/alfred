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

### production
With a [traefik](https://containo.us/traefik/) instance running:
`./alfred prod`


### design
Alfred is built around the concept of a single track video editor, which holds a rearrangeable series of clips, stacked end to end in time.

- `Clip` - a section of time of a media file. Clips have:
  * `inpoint`:  start time
  * `outpoint`: end time
  * `duration`: (`outpoint` - `inpoint`)
  * `description`: text
- `Edl` - an ordered list of Clips.
- `Timeline` - a visual representation of an `Edl` with clips as sortable blocks, sized proportionately to the duration of the clip, and reflowed according to the available space in the window.
- `Project` - an editable table of values of the `Edl`
- `Projects` - a list of available `Edl`s to load
- `Bin` - a list of available media to use in the `Timeline`
