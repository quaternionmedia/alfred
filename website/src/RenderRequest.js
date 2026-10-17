import { auth } from './Login'
import { Edl, clipSeconds } from './Video'
import { RenderStatus } from './RenderStatus'

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
 * otto's default of five seconds.
 */
export function timelineEdl(clips) {
  let start = 0
  const placed = []
  for (const clip of clips || []) {
    if (!clip) continue
    // `i` is the view's index, written onto each clip as it is drawn. It
    // means nothing to the server.
    const { i, ...rest } = clip
    const duration = clipSeconds(clip)
    placed.push({ ...rest, duration, start })
    start += duration
  }
  return { clips: placed, duration: start }
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
