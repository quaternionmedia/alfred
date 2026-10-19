import { auth } from './Login'
import { describeDetail } from './Problem'
import { authJson, expired, usable } from './Signed'

/**
 * Bytes that need the session to fetch, and handing them to the browser.
 *
 * The session token travels in an Authorization header, which a browser-issued
 * request -- an `<a href>`, an `<img src>`, a `<video src>` -- never carries.
 * So a protected file is fetched here, with the token, and the element (or the
 * download) is given an object URL for the bytes instead.
 *
 * That is the fallback now. Where the server issues a signed URL for a file
 * (contract M1, Signed.js) the browser is handed that and fetches the file by
 * itself; this path serves a server that does not, or a file it did not sign.
 *
 * Built on `auth()` rather than beside it, so a protected file gets the same
 * session handling as every other request, whatever `auth()` does about an
 * expired session; nothing here knows about tokens. That only works if a
 * failed request rejects with the HTTP status on `.code`, which is what
 * `auth()` reads to tell an expired session from anything else -- so
 * `extract` below throws exactly that.
 */

/** The filename a `Content-Disposition` header proposes, or null. */
export function dispositionFilename(header) {
  if (!header) return null
  // RFC 5987 form first (`filename*=UTF-8''...`): it is the one that can carry
  // a name that is not plain ASCII, and servers send it alongside the other.
  const extended = /filename\*\s*=\s*([\w-]+)'[^']*'([^;]+)/i.exec(header)
  if (extended) {
    try {
      return decodeURIComponent(extended[2].trim().replace(/^"|"$/g, ''))
    } catch (e) {
      // malformed escape: fall through to the plain form
    }
  }
  const plain = /filename\s*=\s*(?:"([^"]*)"|([^;]+))/i.exec(header)
  if (plain) return (plain[1] !== undefined ? plain[1] : plain[2]).trim() || null
  return null
}

/** GET `url` with the session, as a Blob: resolves `{blob, filename, type}`. */
export function authBlob(url, opts) {
  return auth(url, {
    ...opts,
    responseType: 'blob',
    // With a custom `extract`, mithril resolves whatever the status was; a
    // failure has to be thrown from here to reject at all.
    extract: xhr => {
      if (xhr.status < 200 || xhr.status >= 300) {
        const err = new Error(`${url} answered ${xhr.status}`)
        err.code = xhr.status
        // The server's explanation, still a Blob: `responseText` cannot be
        // read when the response type is 'blob' -- it throws -- which is how
        // the template preview lost every 422 reason it was sent.
        err.body = xhr.response
        // When a busy server says to ask again (a 503 with Retry-After): the
        // preview routes do, once they are drawing as many as they will.
        err.retryAfter = xhr.getResponseHeader('Retry-After')
        throw err
      }
      return {
        blob: xhr.response,
        filename: dispositionFilename(xhr.getResponseHeader('Content-Disposition')),
        type: xhr.getResponseHeader('Content-Type'),
      }
    },
  })
}

/** What a rejected `authBlob` request's server said, as one line ('' if nothing). */
export function blobProblem(err) {
  const body = err && err.body
  if (!body || typeof body.text !== 'function') return Promise.resolve('')
  return body.text().then(
    text => {
      try {
        return describeDetail(JSON.parse(text).detail)
      } catch (e) {
        return ''
      }
    },
    () => ''
  )
}

/**
 * How long a busy server asked to be left before it is asked again, in
 * milliseconds, from a rejected `authBlob`; null unless it answered 503 with a
 * Retry-After header. The header is seconds or an HTTP date. Kept between one
 * second and a minute, so a header of 0 cannot make a caller ask in a loop.
 */
export function retryAfterMs(err) {
  if (!err || err.code !== 503 || !err.retryAfter) return null
  const header = String(err.retryAfter).trim()
  const ms = /^\d+$/.test(header) ? Number(header) * 1000 : Date.parse(header) - Date.now()
  if (!Number.isFinite(ms)) return null
  return Math.min(Math.max(ms, 1000), 60 * 1000)
}

/** Offer a blob to the person as a file to save. */
export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'download'
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  // Not revoked straight away: the download reads from this URL after the
  // click returns, and revoking it first can cancel the download.
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}

/** Hand the browser a URL to download by itself, under the server's name for it. */
export function saveUrl(url) {
  const a = document.createElement('a')
  a.href = url
  // Empty, so the `Content-Disposition` the server sends names the file.
  a.setAttribute('download', '')
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

/**
 * A signed download URL for a finished render that is good to use now, or
 * null when the server issues none.
 *
 * The render list and its status both carry `download_url` (contract M1), but
 * a list read when the Deliver stage opened can be older than the URL's
 * lifetime by the time anyone presses Download. One that has run out, or is
 * about to, is asked for again rather than handed to a download that would be
 * refused.
 */
export function freshDownloadUrl(render) {
  const url = render && render.download_url
  if (!url) return Promise.resolve(null)
  if (usable(url, 10 * 1000)) return Promise.resolve(url)
  return authJson(`/render/${render._id}/status`).then(
    status => {
      const renewed = status && status.download_url
      return renewed && !expired(renewed) ? renewed : null
    },
    () => null
  )
}

/**
 * Download a finished render. Resolves to the filename it was saved under,
 * or null when the browser is fetching it under the server's name.
 *
 * Through the render's signed download URL when the server issues one: the
 * browser fetches the file itself, straight to disk, the way any download
 * works. Without one the file is fetched with the session and held in memory
 * on the way through -- fine for seconds of video, and the reason the signed
 * link is preferred.
 */
export function downloadRender(render) {
  return freshDownloadUrl(render).then(url => {
    if (url) {
      saveUrl(url)
      return null
    }
    return authBlob(`/render/${render._id}/download`).then(({ blob, filename }) => {
      const name = filename || `${render.name || render.project || render._id}.mp4`
      saveBlob(blob, name)
      return name
    })
  })
}
