import m from 'mithril'
import { Video, Edl } from './Video'

const urlfy = obj => Object
    .keys(obj)
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]))
    .join('&');

function Image() {
  return {
    view: (vnode) => {
      return m('img', {
        src: vnode.attrs.src,
        style: {
          width: '100%',
          height: '100%'
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
    },
    onupdate: (vnode) => {

    },
    view: (vnode) => {
      let clip = Edl.edl[Edl.current]
      console.log('redrawing preview', vnode, clip, Edl)
      if (clip) {
        if (clip.type == 'template') {
          return m(Image, {
            id: 'preview',
            src: `otto/template/${clip['name']}?${urlfy(clip.data)}&t=${Edl.time}`
          })
        } else {
          return m('#preview')
        }
      }
    }
  }
})
