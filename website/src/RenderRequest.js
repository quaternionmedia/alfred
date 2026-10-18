import { auth } from './Login'
import { Edl } from './Video'
import { RenderStatus } from './RenderStatus'
import { clipSeconds, inOf, toMs, windowed } from './Timing'

var state = require('./Globals').state

/**
 * What the editor sends when it asks for a render.
 *
 * There were two ways to ask -- the Render stage and the toolbar button -- and
 * they built two different requests. Both were wrong in the same way and the
 * toolbar was wrong in a second one. Everything that sends a timeline to the
 * server now goes through the functions here, so there is one request shape
 * to get right rather than one per button.
 */

/**
 * The timeline, placed: the EDL this editor sends to the server.
 *
 * The editor plays its clips one after another -- a single track, each clip
 * starting where the previous one ends (`Edl.startOf`). The renderer does not
 * work that way. otto places every clip by its `start` and layers clips that
 * overlap, and a clip with no `start` starts at 0. The editor added clips
 * without one and sent `{clips, duration}` as it stood, so a timeline of three
 * five-second clips rendered as all three stacked at second 0 for five
 * seconds, then ten seconds of black. What played was not what rendered.
 *
 * So every clip leaves with an explicit `start`: the total length of the clips
 * before it, measured by `clipSeconds`, the same rule the player uses. It is
 * computed here, at the moment of sending, from the order on screen -- never
 * read from the clip. A stored `start` records wherever the clip sat when it
 * was saved, and moving, trimming or cutting a clip makes that stale. The
 * project keeps its timeline exactly as before; only what is sent is placed.
 *
 * `duration` goes out as the number the start was computed from, for the same
 * reason: a clip whose length the editor read as zero must not render for
 * otto's default of five seconds. And a clip with a window goes out with an
 * out-point that agrees with that length: otto plays such a clip from its
 * in-point to its out-point and does not read `duration`, so a stored
 * out-point that disagreed -- a clip saved before trims kept it in step --
 * rendered a different length from the one the editor played.
 *
 * This is also what a project saves (contract M4): the same clips, placed the
 * same way, so a saved `project.edl` renders verbatim to what the editor
 * renders -- for anyone who renders it, not only this page.
 */
export function timelineEdl(clips) {
  let start = 0
  const placed = []
  for (const clip of clips || []) {
    if (!clip) continue
    // `i` is the view's index, written onto each clip as it is drawn. It
    // means nothing to the server.
    const { i, ...rest } = clip
    const duration = toMs(clipSeconds(clip))
    const out = {
      ...rest,
      duration,
      start: toMs(start),
      fadeIn: chosenFade(clip.fadeIn),
      fadeOut: chosenFade(clip.fadeOut),
    }
    if (windowed(clip)) {
      out.inpoint = toMs(inOf(clip))
      out.outpoint = toMs(out.inpoint + duration)
    }
    placed.push(out)
    start += duration
  }
  return { clips: placed, duration: toMs(start) }
}

// otto's default fade for a clip, in seconds -- which the API also writes
// onto every clip it stores, whether or not anyone chose it.
const MODEL_FADE = 1

/**
 * A clip's fade as the render should get it: none, unless one was chosen.
 *
 * The editor plays its timeline as hard cuts. otto fades every clip in and
 * out over a second unless told otherwise, so clips placed end to end would
 * render with a dip to black at every cut that the preview never showed. So
 * a clip with no fade goes out with 0.
 *
 * "No fade" includes a fade of exactly otto's default. The project routes
 * stored clips through otto's model, which filled in the default, so a clip
 * loaded from a project saved before saves went through `timelineEdl` carries
 * `fadeIn: 1` and `fadeOut: 1` that nobody set -- indistinguishable from a
 * chosen one-second fade, and far more likely. Any other value was chosen by
 * someone, and is kept. Saves write the explicit 0 now, so a project once
 * saved from here no longer depends on this guess.
 */
function chosenFade(value) {
  if (value === undefined || value === null || value === '') return 0
  const seconds = Number(value)
  if (!Number.isFinite(seconds) || seconds === MODEL_FADE) return 0
  return Math.max(0, seconds)
}

/**
 * A layered EDL, as a form-driven project's logic builds one.
 *
 * Not a single-track timeline: the logic places its clips deliberately -- a
 * background from 0, captions over it from 17.1 -- and recomputing starts
 * end to end would undo that. So each clip keeps its own `start`, and one
 * without a start leaves with an explicit 0, which is what a missing start
 * already meant to the renderer, said out loud rather than left to a default.
 * The duration is where the last clip ends.
 */
export function layeredEdl(clips) {
  const placed = (clips || [])
    .filter(Boolean)
    .map(({ i, ...clip }) => ({ ...clip, start: Number(clip.start) || 0 }))
  const duration = placed.reduce((end, c) => Math.max(end, c.start + clipSeconds(c)), 0)
  return { clips: placed, duration }
}

/** What a project renders at: the size it was last rendered at, else the viewer's. */
export function renderSize(project) {
  const saved = (project && project.render_settings) || {}
  return {
    width: Number(saved.width) || state.width(),
    height: Number(saved.height) || state.height(),
  }
}

/**
 * The body of `POST /render` for what is on the timeline.
 *
 * Everything in the body, nothing in the query string: the route reads only
 * the body, which is why the toolbar's `?project=&width=&height=` rendered
 * every timeline at 1920x1080 with no project.
 */
export function timelineRender({ project, projectId, width, height }) {
  const edl = timelineEdl(Edl.edl)
  const name = (project && project.name) || 'untitled'
  return {
    edl,
    name,
    project: name,
    project_id: projectId || undefined,
    width: Number(width),
    height: Number(height),
    duration: edl.duration,
  }
}

/** Queue a render and follow it until it settles. Resolves to the new render's id. */
export function queueRender(body) {
  return auth('/render', { method: 'POST', body }).then(raw => {
    // The route returns the id as a JSON string; strip quotes in case a
    // proxy or an older server hands it back double-encoded.
    const id = String(raw).replace(/"/g, '')
    RenderStatus.watch(id, { name: body.name })
    return id
  })
}
