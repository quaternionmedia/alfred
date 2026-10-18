import m from 'mithril'
import { User } from './User'
import { ServerClock, authJson, expired, expiresAt, usable } from './Signed'

/**
 * The media library: what files there are, what they are, how long they run,
 * and the address the browser may fetch each from (contracts M1 and M2).
 *
 * `GET /media` answers all of that in one list:
 *
 *   {name: "videos/<file>", kind: "video"|"image"|"audio", duration, width,
 *    height, fps, size, url}
 *
 * where `duration` is the probed length in seconds (null when it cannot be
 * known -- a still image has none) and `url` is a short-lived signed URL for
 * the file. A server from before that route answers 404, and then this falls
 * back to `GET /videos`, which lists names only: kinds are guessed from the
 * extension, nothing has a known length, and media is fetched with the
 * session as a blob, as it always was.
 *
 * One list for the whole page. The bin and the Source stage each fetched
 * `/videos` for themselves and held their own copy; they read this one now,
 * so the length a clip is added at and the bound a trim stops at come from
 * the same answer.
 */

const KINDS = ['video', 'image', 'audio']

// The extensions the server's media rules accept as each kind
// (`MEDIA_EXTENSIONS` in alfred/core/utils/media.py). Only consulted when the
// server does not say -- the `/videos` fallback.
const IMAGES = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']
const SOUNDS = ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'oga']

/** What a library file is, judged by its name: video, unless it is plainly not. */
export function kindByName(name) {
  const ext = String(name).split('.').pop().toLowerCase()
  if (IMAGES.includes(ext)) return 'image'
  if (SOUNDS.includes(ext)) return 'audio'
  return 'video'
}

/** One entry of either list, in the shape the rest of the page reads. */
function entry(item) {
  if (typeof item === 'string') {
    return { name: item, kind: kindByName(item), duration: null, url: null }
  }
  if (!item || typeof item.name !== 'string' || !item.name) return null
  const duration = Number(item.duration)
  return {
    ...item,
    kind: KINDS.includes(item.kind) ? item.kind : kindByName(item.name),
    duration: item.duration != null && Number.isFinite(duration) && duration > 0 ? duration : null,
    url: typeof item.url === 'string' && item.url ? item.url : null,
  }
}

const list = answer => (Array.isArray(answer) ? answer : []).map(entry).filter(Boolean)

// After a failure, how long before an ordinary ask tries again. Callers ask on
// every redraw, and every answer redraws: retrying at once would turn one
// failing request into a loop.
const RETRY_MS = 5 * 1000
// Fresh signed URLs this long before the soonest runs out.
const RENEW_BEFORE_MS = 60 * 1000
// No more often than this, whatever asks.
const RENEW_AT_MOST_EVERY_MS = 10 * 1000

export const Library = {
  /** Every entry, in the server's order. */
  items: [],
  byName: new Map(),
  /** Which route answered: 'media', 'videos', or null before either has. */
  via: null,
  loaded: false,
  inflight: null,
  retryAt: 0,
  renewedAt: 0,
  timer: null,

  /**
   * Fetch the list, once; again only when `force`d -- new media was made,
   * or signed URLs are running out. Resolves to the items either way.
   */
  load: ({ force = false } = {}) => {
    if (!User.loggedIn) return Promise.resolve(Library.items)
    if (Library.inflight) return Library.inflight
    if (!force && (Library.loaded || Date.now() < Library.retryAt)) {
      return Promise.resolve(Library.items)
    }
    Library.inflight = fetchList()
      .then(
        items => {
          Library.set(items)
          Library.loaded = true
          Library.retryAt = 0
        },
        err => {
          console.error('could not load the media library', err)
          Library.retryAt = Date.now() + RETRY_MS
        }
      )
      .then(() => {
        Library.inflight = null
        m.redraw()
        return Library.items
      })
    return Library.inflight
  },

  set: items => {
    Library.items = items
    Library.byName = new Map(items.map(item => [item.name, item]))
    Library.schedule()
  },

  /** Renew the list shortly before its soonest signed URL runs out. */
  schedule: () => {
    clearTimeout(Library.timer)
    const soonest = Math.min(...Library.items.map(item => expiresAt(item.url) || Infinity))
    if (!Number.isFinite(soonest)) return
    const wait = Math.max(RENEW_AT_MOST_EVERY_MS, soonest - ServerClock.now() - RENEW_BEFORE_MS)
    Library.timer = setTimeout(() => {
      if (User.loggedIn) Library.renew()
    }, wait)
  },

  /** Ask again for fresh signed URLs, at most once every few seconds. */
  renew: () => {
    if (Date.now() - Library.renewedAt < RENEW_AT_MOST_EVERY_MS) return Library.inflight
    Library.renewedAt = Date.now()
    return Library.load({ force: true })
  },

  get: name => Library.byName.get(name),

  /** The library's names, as `GET /videos` lists them. */
  names: () => Library.items.map(item => item.name),

  /** A file's length in seconds, when the server knows it; otherwise null. */
  durationOf: name => {
    const item = Library.byName.get(name)
    return item ? item.duration : null
  },

  /** video, image or audio. */
  kindOf: name => {
    const item = Library.byName.get(name)
    return item ? item.kind : kindByName(name)
  },

  /**
   * Whether `name` is fetched by signed URL rather than as a blob: the
   * server issues them and has one for this file.
   *
   * Before the list has answered that is not known yet, and the answer is
   * worth waiting for: falling back at once would start downloading the
   * whole file as a blob a moment before a URL arrived that streams it. A
   * list that failed to arrive is not waited for.
   */
  signs: name => {
    if (Library.via === 'videos') return false
    if (!Library.loaded) {
      if (Library.retryAt) return false
      Library.load()
      return true
    }
    const item = Library.byName.get(name)
    return Boolean(item && item.url)
  },

  /**
   * The signed URL to fetch `name` from, or null when there is none to use
   * right now.
   *
   * A URL near its expiry is still handed out -- it works for now -- while a
   * fresh list is asked for; one that has run out is not, since every
   * request made with it would be refused.
   */
  urlFor: name => {
    const item = Library.byName.get(name)
    if (!item || !item.url) return null
    if (usable(item.url)) return item.url
    Library.renew()
    return expired(item.url) ? null : item.url
  },
}

/** `GET /media`, or the older `GET /videos` from a server without it. */
function fetchList() {
  if (Library.via === 'videos') return authJson('/videos').then(list)
  return authJson('/media').then(
    answer => {
      Library.via = 'media'
      return list(answer)
    },
    err => {
      if (err && err.code === 404) {
        Library.via = 'videos'
        return fetchList()
      }
      throw err
    }
  )
}
