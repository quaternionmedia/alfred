import m from 'mithril'
import { auth } from './Login'
import { User } from './User'

/**
 * Whether anything is there to render (contract M3).
 *
 * A render is queued for a worker, and with no worker running it stays
 * queued: the Deliver stage showed "queued" and an empty progress bar for as
 * long as anyone watched, indistinguishable from a busy queue, and the page
 * went on asking about it every few seconds. `GET /health` answers
 * `{api, db, renderer: {ok, workers}, queue: {pending}}`, the worker count
 * from a short ping, so the page can say why nothing moves -- and stop asking
 * so often.
 *
 * Asked while a stage that renders is open (Render, Deliver), and again every
 * so often while one is. A server from before the route answers 404, and then
 * nothing is said and nothing is asked again: no answer is not "no renderer".
 */

// While a stage that cares is open. The server caches its ping for a few
// seconds, so asking faster would only read the cache.
const EVERY_MS = 10 * 1000

const emit = down => {
  for (const listener of Health.listeners) {
    try {
      listener(down)
    } catch (e) {
      console.error('health listener failed', e)
    }
  }
}

export const Health = {
  /** The last answer, or null before one (or from a server without the route). */
  state: null,
  /**
   * Whether a check has come back yet: an answer, a 404, or a failure. Until
   * one has, nothing is known -- which is not the same as nothing wrong.
   */
  answered: false,
  /** False once the server has said it has no such route. */
  supported: true,
  watchers: new Set(),
  listeners: [],
  inflight: null,
  timer: null,
  owed: false,

  /** No renderer is running: the server said so, in so many words. */
  rendererDown: () => {
    const renderer = Health.state && Health.state.renderer
    return Boolean(renderer) && renderer.workers === 0
  },

  /** Be told `(down)` whenever whether the renderer is down changes. */
  listen: listener => {
    Health.listeners.push(listener)
  },

  check: () => {
    if (!Health.supported || !User.loggedIn) return Promise.resolve(Health.state)
    if (Health.inflight) return Health.inflight
    const wasDown = Health.rendererDown()
    Health.inflight = auth('/health', { background: true })
      .then(
        answer => {
          Health.state = answer && typeof answer === 'object' ? answer : null
        },
        err => {
          if (err && err.code === 404) {
            Health.supported = false
            Health.state = null
          }
          // Anything else -- a restart, a dropped connection -- says nothing
          // new about the renderer; the last answer stands until the next.
        }
      )
      .then(() => {
        Health.inflight = null
        Health.answered = true
        const down = Health.rendererDown()
        if (down !== wasDown) emit(down)
        m.redraw()
        return Health.state
      })
    return Health.inflight
  },

  /** Keep asking while `who` is open; ask now. */
  watch: who => {
    Health.watchers.add(who)
    // A stage can open before a restored session is confirmed -- on a
    // reload, the first draw comes before `/users/me` answers -- and there is
    // nothing to ask with yet. `catchUp` asks on a later draw, once there is.
    Health.owed = !User.loggedIn
    Health.check()
    if (!Health.timer) {
      Health.timer = setInterval(() => {
        if (Health.watchers.size && User.loggedIn) Health.check()
      }, EVERY_MS)
    }
  },

  /** Ask now if a watcher opened before the session was there to ask with. */
  catchUp: () => {
    if (!Health.owed || !User.loggedIn) return
    Health.owed = false
    Health.check()
  },

  unwatch: who => {
    Health.watchers.delete(who)
    if (!Health.watchers.size && Health.timer) {
      clearInterval(Health.timer)
      Health.timer = null
    }
  },
}

/** What the Render and Deliver stages say when no renderer is running, or nothing. */
export const RendererNotice = {
  view: () =>
    Health.rendererDown()
      ? m(
          'p.stagewarn#renderer-offline',
          { role: 'status' },
          'No renderer is running — renders stay queued'
        )
      : null,
}
