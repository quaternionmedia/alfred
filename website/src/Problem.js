/**
 * What the server said went wrong, as one line a person can read.
 *
 * FastAPI answers a refused request with `{"detail": ...}`, where `detail` is
 * a sentence for errors the code raises itself and a list of `{loc, msg}`
 * objects for validation failures. Both are worth more on screen than "Could
 * not queue the render", which is what every failure used to say whatever the
 * reason -- so a render refused for its settings read exactly like a server
 * that was down.
 */

/** Flatten a `detail` of either shape into a sentence, or '' when there is none. */
export function describeDetail(detail) {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map(d => {
        if (!d || typeof d !== 'object') return String(d)
        const where = Array.isArray(d.loc) ? d.loc.filter(p => p !== 'body').join('.') : ''
        return where ? `${where}: ${d.msg}` : String(d.msg || '')
      })
      .filter(Boolean)
      .join('; ')
  }
  if (typeof detail === 'object' && detail.msg) return String(detail.msg)
  return String(detail)
}

/** The explanation carried by a rejected `auth()`/`m.request` JSON request. */
export function requestProblem(err) {
  const body = err && err.response
  return describeDetail(body && typeof body === 'object' ? body.detail : '')
}
