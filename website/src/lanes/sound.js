import m from 'mithril'
import { auth } from '../Login'
import { refusalCode, requestProblem } from '../Problem'

/**
 * How each library file sounds, for the Audio lane: the audio engine's
 * loudness envelope and silences, by file, from `GET /media/{name}/audio`
 * (docs/captions.md, "Analysing library media"). Asked once per file while the
 * page is open; a file that could not be analysed says why, and is asked
 * again only by `retry`.
 */

const FEATURES = 'peaks,silences'

const path = name => `/media/${String(name).split('/').map(encodeURIComponent).join('/')}/audio`

export const Sound = {
  /** By file name: `{state, peaks, silences, why}`. `state` is `asking`,
   * `heard`, `silent` (no sound to draw), `no-engine` or `failed`. */
  byName: new Map(),

  /** What is known of `name`, asking if nothing is yet. */
  of: name => {
    if (!name) return null
    const known = Sound.byName.get(name)
    if (known) return known
    const entry = { state: 'asking', peaks: null, silences: [], why: null }
    Sound.byName.set(name, entry)
    // `background`: the answer redraws once it is in, not before.
    auth(`${path(name)}?features=${FEATURES}`, { background: true })
      .then(answer => {
        const peaks = answer && answer.peaks
        const values = peaks && Array.isArray(peaks.values) ? peaks.values : []
        entry.peaks = values.length ? peaks : null
        entry.silences = (answer && answer.silences) || []
        entry.state = values.length ? 'heard' : 'silent'
      })
      .catch(err => {
        const code = refusalCode(err)
        entry.state =
          code === 'audio_engine_missing' ? 'no-engine' : code === 'media_silent' ? 'silent' : 'failed'
        entry.why = requestProblem(err) || 'no answer'
      })
      .then(() => m.redraw())
    return entry
  },

  /** Forget what could not be analysed, so the lane asks again. */
  retry: () => {
    for (const [name, entry] of Sound.byName) {
      if (entry.state === 'failed' || entry.state === 'no-engine') Sound.byName.delete(name)
    }
  },

  reset: () => Sound.byName.clear(),
}
