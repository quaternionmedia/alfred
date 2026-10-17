import { success, error } from 'alertifyjs'
import { auth } from './Login'
import { User } from './User'
import { escapeHtml } from './Problem'

/**
 * Where a render is, kept current.
 *
 * Nothing polled before. The render list was fetched once per visit to the
 * Deliver stage or once per action, so the progress on a row was a snapshot of
 * the moment you arrived: "queued" for as long as you watched, with no way to
 * learn that it had finished or failed short of leaving the stage and coming
 * back. And the reason a render failed was nowhere in the interface at all.
 *
 * A render queued from this page is now watched until it settles. Each one is
 * asked about with `GET /render/{id}/status`, backing off while nothing moves
 * and returning to a quick pace when something does. When it settles the page
 * says so wherever you are, with the failure reason if there is one.
 */

const STATES = ['queued', 'rendering', 'rendered', 'failed']

/** A render that will not change again on its own. */
export const isSettled = state => state === 'rendered' || state === 'failed'

/**
 * The state of a render, derived the way the status route derives it.
 *
 * Accepts either shape: a status response already carries `state`, and a
 * document from `GET /render` carries the raw `status` and `progress` it is
 * derived from -- `failed` if the encode failed, `rendered` once the file
 * exists, `rendering` once progress has started, and `queued` before that.
 */
export function renderState(r) {
  if (!r) return 'queued'
  if (STATES.includes(r.state)) return r.state
  if (r.status === 'failed') return 'failed'
  if (r.status === 'RENDERED' || r.status === 'UPLOADED') return 'rendered'
  if (Number(r.progress) > 0) return 'rendering'
  return 'queued'
}

// Quick while something is moving, patient while nothing is. A render that
// sits queued -- no worker, or a long queue ahead of it -- is asked about less
// and less often, up to the ceiling, rather than once a second forever.
const FIRST_DELAY = 1000
const MAX_DELAY = 10000
const GROWTH = 1.6

/** The fields the rows show, from either response shape. */
function snapshot(r) {
  return {
    state: renderState(r),
    status: r.status === undefined ? null : r.status,
    progress: typeof r.progress === 'number' ? r.progress : null,
    filename: r.filename || null,
    destination: r.destination || null,
    error: r.error || null,
  }
}

function emit(type, id, payload) {
  for (const listener of RenderStatus.listeners) {
    try {
      listener(type, id, payload)
    } catch (e) {
      console.error('render status listener failed', e)
    }
  }
}

function schedule(id, delay) {
  const watch = RenderStatus.watching[id]
  if (!watch) return
  clearTimeout(watch.timer)
  watch.timer = setTimeout(() => poll(id), delay === undefined ? watch.delay : delay)
}

function settle(id, watch, latest) {
  delete RenderStatus.watching[id]
  emit('settled', id, latest)
  const name = escapeHtml(watch.label)
  if (latest.state === 'failed') {
    const why = latest.error ? `: ${escapeHtml(latest.error)}` : ''
    error(`${name} failed${why}`, 12)
  } else {
    success(`${name} is rendered. Download or deliver it from the Deliver stage.`, 8)
  }
}

function poll(id) {
  const watch = RenderStatus.watching[id]
  if (!watch) return
  watch.timer = null
  // A logged-out page has nothing to ask with, and asking anyway would send
  // the visitor to the login screen once per poll.
  if (!User.loggedIn) return RenderStatus.stop(id)

  const ask =
    watch.via === 'status'
      ? auth(`/render/${id}/status`)
      : auth('/render').then(list => {
          emit('list', id, list)
          return (Array.isArray(list) ? list : []).find(r => r._id === id) || null
        })

  ask.then(
    found => {
      if (RenderStatus.watching[id] !== watch) return
      // Only the list can come back without it: deleted, or not ours to see.
      if (!found) return RenderStatus.stop(id)

      const before = RenderStatus.live[id] || {}
      const latest = { ...before, ...snapshot(found), id }
      RenderStatus.live[id] = latest
      if (isSettled(latest.state)) return settle(id, watch, latest)

      const moved = before.state !== latest.state || before.progress !== latest.progress
      watch.delay = moved ? FIRST_DELAY : Math.min(watch.delay * GROWTH, MAX_DELAY)
      emit('update', id, latest)
      schedule(id)
    },
    err => {
      if (RenderStatus.watching[id] !== watch) return
      const code = err && err.code
      // The session is over, and auth() has already sent them to log in. A
      // malformed id will never become a good one.
      if (code === 401 || code === 422) return RenderStatus.stop(id)
      // No status route on this server, or no such render: the list answers
      // both, so ask it instead -- straight away, not after a back-off.
      if (watch.via === 'status' && code === 404) {
        watch.via = 'list'
        return schedule(id, 0)
      }
      // Anything else is worth another try, less eagerly.
      watch.delay = Math.min(watch.delay * GROWTH, MAX_DELAY)
      schedule(id)
    }
  )
}

export const RenderStatus = {
  /** id -> the latest known `{id, state, status, progress, filename, destination, error}`. */
  live: {},
  /** id -> `{via, delay, timer, label}` for renders still being asked about. */
  watching: {},
  listeners: [],

  get: id => RenderStatus.live[id],

  isWatching: id => Boolean(RenderStatus.watching[id]),

  /** Be told `(type, id, payload)` for 'watching', 'update', 'list' and 'settled'. */
  listen: listener => {
    RenderStatus.listeners.push(listener)
  },

  /** Follow a render until it is rendered or has failed. */
  watch: (id, { name } = {}) => {
    if (!id) return
    RenderStatus.stop(id)
    RenderStatus.live[id] = {
      id,
      state: 'queued',
      status: null,
      progress: null,
      error: null,
      ...RenderStatus.live[id],
    }
    RenderStatus.watching[id] = {
      via: 'status',
      delay: FIRST_DELAY,
      timer: null,
      label: name ? `"${name}"` : 'The render',
    }
    emit('watching', id, RenderStatus.live[id])
    schedule(id, FIRST_DELAY / 2)
  },

  stop: id => {
    const watch = RenderStatus.watching[id]
    if (!watch) return
    clearTimeout(watch.timer)
    delete RenderStatus.watching[id]
  },
}
