import { auth } from './Login'
import { describeDetail } from './Problem'

/**
 * Bytes that need the session to fetch, and handing them to the browser.
 *
 * The session token travels in an Authorization header, which a browser-issued
 * request -- an `<a href>`, an `<img src>`, a `<video src>` -- never carries.
 * So a protected file is fetched here, with the token, and the element (or the
 * download) is given an object URL for the bytes instead.
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

/**
 * Download a finished render. Resolves to the filename it was saved under.
 *
 * The whole file is held in memory on the way through. Renders here are
 * seconds to minutes long, so that is fine; a long-form render would want a
 * short-lived signed link the browser can fetch by itself instead.
 */
export function downloadRender(render) {
  return authBlob(`/render/${render._id}/download`).then(({ blob, filename }) => {
    const name = filename || `${render.name || render.project || render._id}.mp4`
    saveBlob(blob, name)
    return name
  })
}
