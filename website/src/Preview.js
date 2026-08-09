import m from 'mithril'
import { Video, Edl } from './Video'
import { Player } from './Player'
import { User } from './User'
var state = require("./Globals").state

const urlfy = obj => Object
    .keys(obj)
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]))
    .join('&');

export function ImagePreview() {
  return {
    view: (vnode) => {
      return m('img.preview', {
        src: vnode.attrs.src
      })
    }
  }
}

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
export function AuthedImage() {
  let objectUrl = null
  let lastRequested = null

  const release = () => {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl)
      objectUrl = null
    }
  }

  const load = url => {
    if (url === lastRequested) return
    lastRequested = url
    m.request({
      url,
      headers: { Authorization: User.token },
      responseType: 'blob',
      extract: xhr => xhr.response,
    })
      .then(blob => {
        release()
        objectUrl = URL.createObjectURL(blob)
        m.redraw()
      })
      .catch(() => {
        // A template that cannot render is not worth a broken-image icon on
        // every redraw; leave the previous frame up.
      })
  }

  return {
    oninit: vnode => load(vnode.attrs.src),
    onupdate: vnode => load(vnode.attrs.src),
    onremove: release,
    view: vnode =>
      objectUrl
        ? m('img.preview', { id: vnode.attrs.id, src: objectUrl })
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
        // The source arrives well after the element does -- it is fetched with
        // the session token and handed over as an object URL -- so the
        // playhead has usually moved on by the time there is anything to show.
        Player.syncElement(true)
        if (Player.playing) Player.resume()
      })
      // The element pausing itself (buffering exhausted, source replaced) must
      // not leave the toolbar showing a pause icon over a stopped video.
      vnode.dom.addEventListener('ended', () => {
        if (Player.playing) Player.pause()
      })
    },

    onremove: vnode => Player.detach(vnode.dom),

    view: vnode => {
      return m('video.preview', {
        ...vnode.attrs,
        // `src` comes from authedSource below, never straight from the clip.
        src: authedSource(vnode.attrs.src),
        style: {
          width: '100%',
          height: '100%',
          'object-fit': 'contain',
        },
      })
    },
  }
}

// Media the browser cannot fetch on its own.
//
// A selected video clip rendered `<video src="videos/x.mp4">`, and /videos
// requires a session -- so the element requested the file with no
// Authorization header, got 401, and showed nothing. Selecting media in the
// bin appeared to do nothing at all.
//
// Same fix as AuthedImage: fetch with the token and hand the element an object
// URL. Fine for the demo clips, which are seconds long; a long edit would want
// range requests, and this loads the whole file before playing. That is the
// trade recorded here rather than discovered later.
const objectUrls = new Map()

export function authedSource(path) {
  if (!path) return undefined
  if (objectUrls.has(path)) return objectUrls.get(path)

  // Mark it pending so a redraw storm does not start a fetch per frame.
  objectUrls.set(path, undefined)
  m.request({
    url: path.startsWith('/') ? path : `/${path}`,
    headers: { Authorization: User.token },
    responseType: 'blob',
    extract: xhr => xhr.response,
  })
    .then(blob => {
      objectUrls.set(path, URL.createObjectURL(blob))
      m.redraw()
    })
    .catch(() => {
      objectUrls.delete(path)
    })
  return undefined
}


export var Preview = () => {
  // One handler, removed on unmount.
  //
  // These were added to `document` in `oncreate` with no matching `onremove`,
  // so navigating away and back left the previous one attached and a single
  // arrow press seeked twice, then three times. They also called `Edl.time()`
  // -- `Edl.time` is a number -- so each one threw before it could do
  // anything, which is the only reason the duplication never showed.
  let onkeydown = null

  return {
    oncreate: () => {
      onkeydown = e => {
        // Not while typing: these keys belong to the field that has focus.
        const tag = (document.activeElement || {}).tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA') return
        if ((document.activeElement || {}).isContentEditable) return

        switch (e.code) {
          case 'Space':
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
        }
      }
      document.addEventListener('keydown', onkeydown)
    },

    onremove: () => {
      if (onkeydown) document.removeEventListener('keydown', onkeydown)
      onkeydown = null
    },

    view: () => {
      const clip = Edl.edl[Edl.current]
      if (!clip) {
        return m('.preview.empty#preview', 'Nothing on the timeline yet.')
      }
      if (clip.type == 'template') {
        // `preview/template/...`, not `otto/template/...`. The latter has
        // never been a route on this server, so previewing a template clip
        // 404'd every time; the endpoint now lives under the preview router
        // and validates the name against the template allowlist.
        return m('.bkg#preview', {}, [
          m(AuthedImage, {
            id: 'preview',
            src: `preview/template/${encodeURIComponent(clip['name'])}?${urlfy(
              clip.data
            )}&width=${state.width()}&height=${state.height()}&t=${Video.time()}`,
          }),
        ])
      }
      // Deliberately unkeyed. This branch alternates with two unkeyed ones
      // above, and mithril refuses a fragment whose children are only
      // partly keyed -- it throws during render and takes the whole subtree
      // with it, which is a failure this codebase has already paid for once.
      return m(VideoPreview, { id: 'preview', src: clip.name })
    },
  }
}
