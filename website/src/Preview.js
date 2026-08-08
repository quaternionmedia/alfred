import m from 'mithril'
import { Video, Edl } from './Video'
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
    onbeforeupdate: (vnode, old) => {
      return Video.paused
    },
    oncreate: (vnode) => {
      document.addEventListener('keydown', e => {
        switch (e.code) {
          case 'Space':
            e.preventDefault()
            if (Video.paused) {
              vnode.dom.play()
              Video.paused = false
              vnode.dom.addEventListener('timeupdate', (e) => {
                Video.time(e.target.currentTime)
                Edl.time(Video.time + Edl.durations(Edl.edl.slice(0,Edl.current)))
                m.redraw()
              })
            } else {
              vnode.dom.pause()
              Video.paused = true
            }
            m.redraw()
            break
          }
        })
      vnode.dom.addEventListener('loadeddata', (event) => {
        if (!Video.paused && vnode.dom.paused) {
          console.log('fixing paused video by playing')
          vnode.dom.play()
        }
        if (Video.time() < Edl.edl[Edl.current]['inpoint']) {
          console.log('jumping to inpoint')
          vnode.dom.currentTime = Video.time()
        }
      })
    },
    view: (vnode) => {
      return m('video.preview', {
        ...vnode.attrs,
        currentTime: Video.time(),
        // state: Video.paused ? vnode.dom.pause() : vnode.dom.play(),
        style: {
          width: '100%',
          height: '100%',
          'object-fit': 'contain'
        }
      })
    }
  }
}


export var Preview = ( () => {
  return {
    oncreate: (vnode) => {
      document.addEventListener('keydown', e => {
        switch (e.code) {
          case 'ArrowLeft':
            console.log('left!', e)
            e.preventDefault()
            Edl.jump(Math.max(Edl.time() - 5, 0))
            break
          case 'ArrowRight':
            e.preventDefault()
            Edl.jump(Math.min(Edl.time() + 5, Edl.duration()))
            break
        }
    })},
    onupdate: (vnode) => {

    },
    view: (vnode) => {
      let clip = Edl.edl[Edl.current]
      if (clip) {
        if (clip.type == 'template') {
          // `preview/template/...`, not `otto/template/...`. The latter has
          // never been a route on this server, so previewing a template clip
          // 404'd every time; the endpoint now lives under the preview router
          // and validates the name against the template allowlist.
          //
          // The `bkg/` background-image that used to wrap this is gone for the
          // same reason -- no such route ever existed -- and it contributed
          // nothing but a second 404 per redraw.
          return m('.bkg#preview', {}, [
            m(AuthedImage, {
              id: 'preview',
              src: `preview/template/${encodeURIComponent(clip['name'])}?${urlfy(clip.data)}&width=${state.width()}&height=${state.height()}&t=${Video.time()}`,
            }),
          ])
        } else {
            return m(VideoPreview, {
              id: 'preview',
              src: clip.name
            })
        }
      }
    }
  }
})
