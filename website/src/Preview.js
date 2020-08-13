import m from 'mithril'
import { Video, Edl } from './Video'
var state = require("./Globals").state

export const urlfy = obj => Object
    .keys(obj)
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]))
    .join('&');

export function ImagePreview() {
  return {
    view: (vnode) => {
      return m('img.preview', {
        ...vnode.attrs
      })
    }
  }
}
export function VideoPreview() {
  return {
    oncreate: (vnode) => {
      vnode.dom.addEventListener('loadeddata', (event) => {
        if (!state.paused() && vnode.dom.paused) {
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
        // state: state.paused() ? vnode.dom.pause() : vnode.dom.play(),
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
    onbeforeupdate: (vnode, old) => {
      return state.paused()
    },
    oncreate: (vnode) => {
      document.addEventListener('keydown', e => {
        switch (e.code) {
          case 'ArrowLeft':
            console.log('left!', e)
            e.preventDefault()
            Edl.jump(Math.max(Edl.time - 5, 0))
            break
          case 'ArrowRight':
            e.preventDefault()
            Edl.jump(Math.min(Edl.time + 5, Edl.duration()))
            break
          case 'Space':
            e.preventDefault()
            Edl.play()
            break
        }
    })},
    onupdate: (vnode) => {

    },
    view: (vnode) => {
      let clip = Edl.edl[Edl.current]
      if (clip) {
        if (clip.type == 'template') {
          return m('.bkg#bkg', {
            style: {
              'background-image': `url(${Edl.media[Math.floor(Edl.time/5)]})`
            }
          }, [m(ImagePreview, {
            id: 'preview',
            onupdate: v => {
              v.dom.src = `otto/template/${clip['name']}?${urlfy(clip.data)}&width=${state.width()}&height=${ state.height()}&t=${Video.time().toFixed(2)}`
            },
          })
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
