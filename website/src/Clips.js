import { Edl } from './Video'
import { Player } from './Player'
import { Library } from './Library'
import { toMs } from './Timing'

/**
 * New clips, and putting them on the timeline.
 *
 * Every way of adding a clip -- the Source stage's lists, the bin's add
 * buttons, a drag from the bin -- builds it here, so a clip looks the same
 * whichever way it arrived. They did not: a clip dragged from the bin was ten
 * seconds long in the bin and five on the timeline, with its fields read back
 * out of DOM attributes as strings.
 */

// How long a clip is when nothing says how long its source is: a template,
// which is drawn for as long as it is asked to be; a still image; and a file
// the server could not measure -- or a server from before `GET /media`, which
// measures nothing. Five seconds matches the demo templates; the trim tool
// adjusts it.
export const DEFAULT_CLIP_SECONDS = 5

// What a new text template says until someone changes it. Visible on the
// clip and in the frame, so a fresh title card reads as a placeholder rather
// than as an empty, apparently broken frame.
export const DEFAULT_TEMPLATE_TEXT = 'Your text here'

/**
 * A clip of a file from the library: the whole of it, from its start.
 *
 * As long as the file, when the library knows how long that is (`GET
 * /media`). Every library clip arrived as five seconds, because nothing
 * reported a length: a three-second demo clip ran two seconds past its end,
 * held on its last frame, and a long one was cut to its first five seconds.
 *
 * Of the kind the library says: an image is a still -- a length and no window
 * onto anything -- and audio is heard, not seen. Both were sent as `video`.
 */
export function mediaClip(name) {
  const kind = Library.kindOf(name)
  if (kind === 'image') return { name, type: 'image', duration: DEFAULT_CLIP_SECONDS }
  const known = Library.durationOf(name)
  // To the millisecond, rounded down: a window must not end past its source.
  const seconds = known ? Math.floor(known * 1000) / 1000 : DEFAULT_CLIP_SECONDS
  return { name, type: kind, inpoint: 0, outpoint: toMs(seconds), duration: toMs(seconds) }
}

/**
 * A clip of a template, from an entry of `GET /templates` or a bare name.
 *
 * `/templates` describes templates -- name, description, the parameters each
 * takes -- not clips: there is no `type`, `duration` or `data` on an entry.
 * Those are supplied here. Text goes in only for a template that takes text
 * (`makeColor` does not), and when the parameters are unknown.
 */
export function templateClip(template) {
  const name = typeof template === 'string' ? template : template.name
  const parameters = template && Array.isArray(template.parameters) ? template.parameters : null
  const takesText = !parameters || parameters.includes('text')
  return {
    type: 'template',
    name,
    duration: DEFAULT_CLIP_SECONDS,
    data: takesText ? { text: DEFAULT_TEMPLATE_TEXT } : {},
  }
}

/**
 * Put a clip on the timeline -- at `index`, or on the end -- and show it.
 *
 * The playhead moves to the new clip, so the viewer shows what was added.
 * Adding something while the viewer kept showing something else read as the
 * click not having worked. Returns the index it landed at.
 */
export function addClip(clip, index) {
  const at =
    index === undefined || index === null
      ? Edl.edl.length
      : Math.max(0, Math.min(Number(index), Edl.edl.length))
  Edl.edl = [...Edl.edl.slice(0, at), clip, ...Edl.edl.slice(at)]
  Player.pause()
  Edl.jump(Edl.startOf(at))
  return at
}
