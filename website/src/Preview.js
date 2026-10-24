import m from 'mithril'
import { Video, Edl } from './Video'
import { Player } from './Player'
import { authBlob, blobProblem, retryAfterMs } from './Download'
import { cutAtPlayhead } from './TimelineTools'
import { Library } from './Library'
import { isSigned } from './Signed'
var state = require("./Globals").state

const urlfy = obj => Object
    .keys(obj || {})
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]))
    .join('&');

/** The length a render builds a template clip to: its outpoint, else its
 * duration. Sent with the preview so the server builds the template the same
 * way; a template paced by its length draws a different frame at the same `t`
 * when it is built shorter. */
const builtLength = clip => {
  const outpoint = Number(clip.outpoint)
  if (outpoint > 0) return outpoint
  const duration = Number(clip.duration)
  return duration > 0 ? duration : null
}

/** The frame of a template clip at the playhead, at the viewer's size. */
export const templatePreviewUrl = clip => {
  const length = builtLength(clip)
  return (
    `preview/template/${encodeURIComponent(clip['name'])}?${urlfy(
      clip.data
    )}&width=${state.width()}&height=${state.height()}&t=${Video.time()}` +
    (length ? `&length=${length}` : '')
  )
}

/** The latest verdict on the template frame in the viewer.
 *
 * Read by the template settings beside it, which show the server's reason a
 * frame will not render next to the fields that caused it.
 */
export const TemplatePreview = { src: null, problem: null }

// An <img> whose source needs the Authorization header.
//
// A bare `src` is a browser-issued request carrying no header, so pointing one
// at an authenticated route just yields a 401 and a broken image. That is the
// constraint main.py records next to the /data mount -- "we can't secure the
// /data route because the otto preview is rendered into the <img> tag" -- and
// the reason a preview route would otherwise have to be left open.
//
// Fetching with the token and handing the <img> an object URL keeps the route
// authenticated. The URL is revoked when it is replaced or the component is
// removed; without that, every redraw of a moving playhead leaks a blob.
//
// One request at a time, always converging on the newest `src`. Every
// playhead move and every keystroke in a template's text is a new frame URL,
// and each was fetched at once: a request per frame while playing, answered
// in whatever order the server finished them -- so an older frame could land
// last and stay up. Now a change while a frame is in flight waits for it, and
// then the newest URL is fetched; anything in between is skipped.
//
// And not again until a busy server says. The server draws only so many
// previews at once and turns the rest away -- 503, with a Retry-After header
// -- once they have waited their turn for a while. Asked again at once, it
// would only be asked again and again; so the frame waits as long as the
// header says, keeping what is on screen, and is then asked for once: the
// newest, whatever the playhead did meanwhile.
export function AuthedImage() {
  let objectUrl = null
  let wanted = null
  let shown = null
  let inflight = false
  let removed = false
  let problem = null
  let busy = false
  let retry = null
  let attrs = {}

  const release = () => {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl)
      objectUrl = null
    }
  }

  const report = verdict => {
    if (typeof attrs.onstate === 'function') attrs.onstate(verdict)
  }

  const askAgainAfter = ms => {
    busy = true
    retry = setTimeout(() => {
      retry = null
      if (removed) return
      busy = false
      m.redraw()
      fetchLatest()
    }, ms)
  }

  const fetchLatest = () => {
    const url = wanted
    if (inflight || retry || !url || url === shown) return
    inflight = true
    authBlob(url)
      .then(
        ({ blob }) => {
          if (removed) return
          release()
          problem = null
          busy = false
          objectUrl = URL.createObjectURL(blob)
          shown = url
          report({ src: url, problem: null })
        },
        // Say why, rather than leaving the last good frame up. The server
        // answers 422 with the reason a template refused, and that reason is
        // worth more on screen than a stale frame -- but it never arrived:
        // reading `responseText` on a blob response throws, so the reason
        // was lost and every refusal read "could not be rendered".
        //
        // Except when the server is only busy: nothing is wrong with the
        // frame, so nothing is reported against it, and it is asked for again
        // when the server says.
        err => {
          const wait = retryAfterMs(err)
          if (wait !== null) {
            if (!removed) askAgainAfter(wait)
            return
          }
          return blobProblem(err).then(detail => {
            if (removed) return
            release()
            problem = detail || 'This template could not be rendered.'
            busy = false
            shown = url
            report({ src: url, problem })
          })
        }
      )
      .catch(e => console.error('template preview failed', e))
      .then(() => {
        inflight = false
        if (removed) return
        m.redraw()
        fetchLatest()
      })
  }

  const want = vnode => {
    attrs = vnode.attrs
    wanted = vnode.attrs.src
    fetchLatest()
  }

  return {
    oninit: want,
    onupdate: want,
    onremove: () => {
      removed = true
      if (retry) clearTimeout(retry)
      retry = null
      release()
    },
    view: vnode =>
      objectUrl
        ? m('img.preview', { id: vnode.attrs.id, src: objectUrl })
        : busy
          ? m('.preview.busy', { id: vnode.attrs.id }, [
              m('i.material-icons', 'hourglass_top'),
              m('span', 'The server is busy with other previews; asking again in a moment.'),
            ])
          : problem
          ? m('.preview.unrenderable', { id: vnode.attrs.id }, [
              m('i.material-icons', 'report_problem'),
              m('span', problem),
            ])
          : m('.preview.loading'),
  }
}
export function VideoPreview() {
  return {
    // No `onbeforeupdate` guard. There was one returning `Video.paused`, to
    // stop redraws resetting `src` and `currentTime` mid-playback -- but the
    // view no longer writes `currentTime` at all, and freezing the component
    // while playing means crossing from one clip to the next never updates
    // `src`, so playback stays on the first file for the whole timeline.

    // Registering the element is the whole point of this component as far as
    // the transport is concerned: it is the only `<video>` the app owns, and
    // the transport had no way to reach it.
    oncreate: vnode => {
      Player.attach(vnode.dom)
      vnode.dom.addEventListener('loadeddata', () => {
        // The source arrives after the element does -- a signed URL once the
        // library has answered, or a blob once the whole file has -- so the
        // playhead has usually moved on by the time there is anything to show.
        Player.syncElement(true)
        if (Player.playing) Player.resume()
      })
      // The element pausing itself (buffering exhausted, source replaced) must
      // not leave the toolbar showing a pause icon over a stopped video.
      vnode.dom.addEventListener('ended', () => {
        if (Player.playing) Player.pause()
      })
      // A signed URL refused -- run out while the page sat idle, or the key
      // changed -- is renewed rather than left as a broken frame.
      vnode.dom.addEventListener('error', () => {
        if (isSigned(vnode.dom.getAttribute('src'))) Library.renew()
      })
    },

    onremove: vnode => Player.detach(vnode.dom),

    view: vnode => {
      return m('video.preview', {
        ...vnode.attrs,
        // `src` comes from mediaSource below, never straight from the clip.
        src: mediaSource(vnode.attrs.src),
        style: {
          width: '100%',
          height: '100%',
          'object-fit': 'contain',
        },
      })
    },
  }
}

/**
 * Where an element should fetch the media named `name` from.
 *
 * A library file comes from the signed URL `GET /media` issued for it
 * (contract M1): the element fetches that itself, with Range requests, so a
 * video starts playing and seeking before it has downloaded -- and nothing
 * holds the whole file in memory. Until the library has answered there is
 * nothing to hand over; waiting for it beats starting a whole-file download
 * a moment before a URL that streams arrives.
 *
 * Without one -- a server from before `/media`, or a file it did not sign --
 * the file is fetched with the session and handed over as a blob, as it was.
 * A remote URL is fetched by the element itself, as it always was.
 */
export function mediaSource(name) {
  if (!name) return undefined
  if (/^https?:\/\//i.test(name)) return name
  const signed = Library.urlFor(name)
  if (signed) return signed
  if (Library.signs(name)) return undefined
  return authedSource(name)
}

// Media the browser cannot fetch on its own: the fallback.
//
// A selected video clip rendered `<video src="videos/x.mp4">`, and /videos
// requires a session -- so the element requested the file with no
// Authorization header, got 401, and showed nothing. Selecting media in the
// bin appeared to do nothing at all.
//
// Same fix as AuthedImage: fetch with the token and hand the element an object
// URL. It loads the whole file before playing, which is why a signed URL is
// preferred whenever the server issues one (mediaSource above).
const objectUrls = new Map()

export function authedSource(path) {
  if (!path) return undefined
  // A remote URL is fetched by the element itself. It is not ours to
  // authenticate against, and the session token must never be sent to
  // another host.
  if (/^https?:\/\//i.test(path)) return path
  if (objectUrls.has(path)) return objectUrls.get(path) || undefined

  // Mark it pending so a redraw storm does not start a fetch per frame.
  objectUrls.set(path, null)
  authBlob(path.startsWith('/') ? path : `/${path}`)
    .then(({ blob }) => {
      objectUrls.set(path, URL.createObjectURL(blob))
      m.redraw()
    })
    .catch(err => {
      console.error('could not load media for the preview', path, err)
      // Not forgotten at once. Deleting the entry straight away let the next
      // redraw ask again, and every answer redraws: a missing file was
      // requested in a loop. Asking again after a pause still recovers from
      // a failure that passes.
      setTimeout(() => objectUrls.delete(path), 10000)
    })
  return undefined
}


const PRESSABLE = ['BUTTON', 'A', 'SUMMARY']

export var Preview = () => {
  // One handler, removed on unmount.
  //
  // These were added to `document` in `oncreate` with no matching `onremove`,
  // so navigating away and back left the previous one attached and a single
  // arrow press seeked twice, then three times. They also called `Edl.time()`
  // -- `Edl.time` is a number -- so each one threw before it could do
  // anything, which is the only reason the duplication never showed.
  let onkeydown = null

  // How the focus arrived where it is: with a pointer press, or otherwise --
  // the keyboard, or a script. Space presses a control the keyboard moved to,
  // and is play and pause on one that merely kept the focus after a click.
  //
  // Recorded rather than read from `:focus-visible`, which looked like the
  // same question and is not: Chrome makes the focused element focus-visible
  // as soon as any key is pressed, so by the time this handler asks, a button
  // that was clicked answers as though the keyboard had moved to it.
  let pressed = null
  let pressedAt = 0
  let pointerFocused = null
  const onpointerdown = e => {
    pressed = e.target
    pressedAt = Date.now()
  }
  const onfocusin = e => {
    // A press focuses what it lands on at once; a stale one (a press on
    // something that takes no focus, long ago) says nothing about this focus.
    const recent = pressed && Date.now() - pressedAt < 1000
    const byPointer =
      recent && (e.target === pressed || (e.target.contains && e.target.contains(pressed)))
    pointerFocused = byPointer ? e.target : null
    pressed = null
  }

  return {
    oncreate: () => {
      document.addEventListener('pointerdown', onpointerdown, true)
      document.addEventListener('focusin', onfocusin, true)
      onkeydown = e => {
        // Not while typing: these keys belong to the field that has focus.
        // A select is a field too -- its arrow keys change its value, and
        // seeking instead made the aspect and resolution menus unusable
        // from the keyboard.
        const focused = document.activeElement || {}
        const tag = focused.tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
        if (focused.isContentEditable) return

        switch (e.code) {
          case 'Space':
            // Space presses a button the keyboard has moved to -- that is how
            // the keyboard operates the timeline tools, and taking the key for
            // play here cancelled the press. A button that merely kept the
            // focus after a click is not that: Space stays play and pause, as
            // someone who just chose a tool with the mouse expects.
            if (PRESSABLE.includes(tag) && focused !== pointerFocused) break
            e.preventDefault()
            Player.toggle()
            break
          case 'ArrowLeft':
            e.preventDefault()
            Player.seek(Math.max(Edl.time - 5, 0))
            break
          case 'ArrowRight':
            e.preventDefault()
            Player.seek(Math.min(Edl.time + 5, Edl.duration()))
            break
          case 'Home':
            e.preventDefault()
            Player.seek(0)
            break
          case 'End':
            e.preventDefault()
            Player.seek(Edl.duration())
            break
          // Split at the playhead, whichever tool is chosen.
          case 'KeyS':
            if (e.ctrlKey || e.metaKey || e.altKey) break
            e.preventDefault()
            cutAtPlayhead()
            break
        }
      }
      document.addEventListener('keydown', onkeydown)
    },

    onremove: () => {
      if (onkeydown) document.removeEventListener('keydown', onkeydown)
      onkeydown = null
      document.removeEventListener('pointerdown', onpointerdown, true)
      document.removeEventListener('focusin', onfocusin, true)
    },

    view: () => {
      const clip = Edl.edl[Edl.current]
      if (!clip) {
        // And where to start. The empty frame is the first thing a new
        // visitor sees, on the Edit stage, and it said only what was missing.
        return m('.preview.empty#preview', [
          m('p', 'Nothing on the timeline yet.'),
          m('p.emptyhint', 'Open a project or add material on the Source stage.'),
        ])
      }
      if (clip.type == 'template') {
        // `preview/template/...`, not `otto/template/...`. The latter has
        // never been a route on this server, so previewing a template clip
        // 404'd every time; the endpoint now lives under the preview router
        // and validates the name against the template allowlist.
        return m('.bkg#preview', {}, [
          m(AuthedImage, {
            id: 'preview',
            src: templatePreviewUrl(clip),
            onstate: verdict => Object.assign(TemplatePreview, verdict),
          }),
        ])
      }
      // A still is a picture, not a video: shown as one, from the same source
      // a video would be.
      if (clip.type == 'image') {
        return m('.bkg#preview', {}, [
          m('img.preview.still', { src: mediaSource(clip.name), alt: '' }),
        ])
      }
      // Deliberately unkeyed. This branch alternates with unkeyed ones
      // above, and mithril refuses a fragment whose children are only
      // partly keyed -- it throws during render and takes the whole subtree
      // with it, which is a failure this codebase has already paid for once.
      return m(VideoPreview, { id: 'preview', src: clip.name })
    },
  }
}
