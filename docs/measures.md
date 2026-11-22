# What is measured

Besides what a person sees and hears, the editor and the programs that drive
it read three measures of the material: how loud the sound is over time, from
the audio engine, and how much the picture moves over time and where it cuts
from one shot to another, from otto. Each is measured per library file, once
per version of the file, and mapped onto a project's timeline through its
clips' windows, so a cut can be placed by where the talking is loud or the
picture is busy, and kept off the middle of a shot. [The timeline's
lanes](lanes.md) draw the sound; the recipes that cut a long recording into
drafts read all three.

| Route | Answers |
|---|---|
| `GET /media/{name}/audio` | the audio engine's analysis of a file: its level over time (`peaks`), its silences, its loudness, tempo, beats and onsets ([Analysing library media](captions.md#analysing-library-media)) |
| `GET /project/{id}/sound` | `{duration, rate, levels, silences}`: the saved timeline's level over time and its silences, in timeline seconds ([The sound of a timeline](captions.md#the-sound-of-a-timeline)) |
| `GET /media/{name}/motion` | `{rate, values}`: how much a file's picture changes over time, 0 to 1, as otto measures it |
| `GET /project/{id}/motion` | `{duration, rate, values}`: the same over the saved timeline, in timeline seconds |
| `GET /media/{name}/scenes` | `{threshold, seconds}`: where a file's picture cuts from one shot to another, each the second a new shot begins, as otto finds them |
| `GET /project/{id}/scenes` | `{duration, seconds}`: the same over the saved timeline, in timeline seconds, each video clip's own edges among them |

## Motion

otto decodes a video's picture a few times a second, reduced to a small grey
picture, and measures how much it changes from one moment to the next: the
mean change over every pixel, as a fraction of black to white
(`otto.media.motion`, in [otto's docs](https://github.com/quaternionmedia/otto/tree/main/docs)).
A still is 0 throughout; a cut from one shot to another is one high value; a
camera that moves, or a figure that crosses the frame, raises the values
while it lasts. The measure says how much the picture moved, not what moved.

On a timeline, each video clip's file is measured once and read through the
clip's window; a still picture, a template and a sound measure 0, and where
clips are stacked the one that moves most is read. The whole file is decoded,
so the first measure of a long recording takes minutes; it is kept
afterwards, as the sound is.

Its refusals ([Refusals](api/errors.md)): 404 for a file the library does not
hold (`not_found`); 422 for an image or an audio file, which has no moving
picture (`no_picture`), for a picture ffmpeg cannot read
(`picture_unreadable`), and for a saved timeline that is empty
(`timeline_empty`) or has no video clip (`no_picture`).

## Scene changes

otto decodes a video's picture a few times a second, reduced small and grey,
and has ffmpeg score each frame by how much of the picture changed from the
frame before; the moments whose score passes a threshold are where a new
shot begins (`otto.media.scenes`, in
[otto's docs](https://github.com/quaternionmedia/otto/tree/main/docs)). A
hard cut is found at any rate; a slow dissolve, a flash or a camera swung
fast may or may not pass, and the measure does not say which happened.

On a timeline, each video clip's file is measured once and its cuts read
through the clip's window, moved to where the clip plays them, and the
clip's own start and end are shots' edges too; a still, a template and a
sound have none. The `scenes` operation of a recipe moves a candidate's
edges to the nearest of these within a second or so, so a draft is not cut
in the middle of a shot. The refusals are motion's, by the same codes.

## What is kept, and where

A measure is kept in the api's memory while it runs, and beside the library
under `.analyses/` in the media directory, a hidden folder that is never
listed or served, so the worker and an api that has restarted read what was
measured rather than measuring again. The key is the file's path, its
modification time and its size, with what was asked of it: a file that
changes is measured again, and nothing is swept, since a measure is a few
kilobytes per hour of material.
