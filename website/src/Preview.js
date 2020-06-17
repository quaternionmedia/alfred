import m from 'mithril'
import { Video, Edl } from './Video'

const urlfy = obj => Object
    .keys(obj)
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]))
    .join('&');

function ImageClip() {
  return {
    view: (vnode) => {
      return m('img', {
        src: vnode.attrs.src,
        style: {
          width: '100%',
          height: '100%',
          'object-fit': 'contain'
        }
      })
    }
  }
}
function VideoClip() {
  return {
    view: (vnode) => {
      return m('video', {
        src: vnode.attrs.src,
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
  let dom = null
  return {
    oncreate: (vnode) => {
      dom = vnode.dom
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
        }
    })},
    onupdate: (vnode) => {

    },
    view: (vnode) => {
      let clip = Edl.edl[Edl.current]
      if (clip) {
        if (clip.type == 'template') {
          return m(ImageClip, {
            id: 'preview',
            src: `otto/template/${clip['name']}?${urlfy(clip.data)}&t=${Video.time}`
          })
        } else {
            return m(VideoClip, {
              id: 'preview',
              src: clip.filename
            })
        }
      }
    }
  }
})
