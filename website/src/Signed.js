/**
 * Signed media URLs (contract M1), as the browser sees them.
 *
 * A signed URL is a short-lived capability for one path:
 * `<path>?exp=<unix seconds>&sig=<signature>`. The browser fetches it by
 * itself -- a `<video src>`, an `<img src>`, a download -- with no
 * Authorization header, which is the point: a video streams with Range
 * requests and seeks, instead of arriving whole as a blob held in memory
 * before the first frame shows.
 *
 * The server issues them only after its own auth and ownership checks; this
 * side only needs to know which URLs are signed, and whether one is still
 * good. "Still good" is judged on the server's clock, learned from the `Date`
 * header of a response, so a browser whose clock is minutes out neither
 * throws away good URLs nor hands an element one that has run out.
 */
import { auth } from './Login'

/** The server's time, as best this page knows it. */
export const ServerClock = {
  // Server time minus this browser's time, in ms.
  offset: 0,

  /** Learn the offset from a response's `Date` header (to the second). */
  observe: header => {
    const at = header ? Date.parse(header) : NaN
    if (Number.isFinite(at)) ServerClock.offset = at - Date.now()
  },

  now: () => Date.now() + ServerClock.offset,
}

/**
 * GET `url` as JSON with the session, noting the server's clock on the way.
 *
 * For the requests that hand out signed URLs. Built on `auth()` like every
 * other request -- a failure rejects with the HTTP status on `.code`, and the
 * parsed body on `.response`, which is what `auth()` and `requestProblem`
 * read -- with an `extract` of its own, since that is the only way to see a
 * response header through `m.request`.
 */
export function authJson(url, opts = {}) {
  return auth(url, {
    ...opts,
    extract: xhr => {
      ServerClock.observe(xhr.getResponseHeader('Date'))
      let body = null
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null
      } catch (e) {
        body = null
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        const err = new Error(`${url} answered ${xhr.status}`)
        err.code = xhr.status
        err.response = body
        throw err
      }
      return body
    },
  })
}

function params(url) {
  try {
    return new URL(url, window.location.href).searchParams
  } catch (e) {
    return null
  }
}

/** A URL carrying an expiry and a signature. */
export function isSigned(url) {
  if (typeof url !== 'string' || !url) return false
  const q = params(url)
  return Boolean(q && q.get('sig') && q.get('exp'))
}

/** When a signed URL stops working, in ms on the server's clock; null if unsigned. */
export function expiresAt(url) {
  if (!isSigned(url)) return null
  const exp = Number(params(url).get('exp'))
  return Number.isFinite(exp) && exp > 0 ? exp * 1000 : null
}

/** Signed, and good for at least `margin` ms more. */
export function usable(url, margin = 30 * 1000) {
  const at = expiresAt(url)
  return at !== null && at - ServerClock.now() > margin
}

/** Signed, and run out (or within `grace` ms of it). */
export function expired(url, grace = 2000) {
  const at = expiresAt(url)
  return at !== null && at - ServerClock.now() <= grace
}
