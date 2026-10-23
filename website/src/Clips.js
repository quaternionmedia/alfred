import { Edl } from './Video'
import { Player } from './Player'

/**
 * New clips, and putting them on the timeline.
 *
 * Every way of adding a clip -- the Source stage's lists, the bin's add
 * buttons, a drag from the bin -- builds it here, so a clip looks the same
 * whichever way it arrived. They did not: a clip dragged from the bin was ten
 * seconds long in the bin and five on the timeline, with its fields read back
 * out of DOM attributes as strings.
 */

// How long a clip is when it arrives.
//
// The server reports which media files exist, not how long they are, and the
// browser cannot know without fetching and decoding each one. Five seconds
// matches the demo clips; the trim tool adjusts it. Worth replacing with a
// real duration from the API, which is the only place that can cheaply know.
export const DEFAULT_CLIP_SECONDS = 5

// What a new text template says until someone changes it. Visible on the
// clip and in the frame, so a fresh title card reads as a placeholder rather
// than as an empty, apparently broken frame.
export const DEFAULT_TEMPLATE_TEXT = 'Your text here'

/** A clip of a media file from the library, from its start. */
export const videoClip = name => ({
  name,
  type: 'video',
  inpoint: 0,
  outpoint: DEFAULT_CLIP_SECONDS,
  duration: DEFAULT_CLIP_SECONDS,
  description: '',
})

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
