import m from 'mithril'
import { Video, Edl } from './Video'

const urlfy = obj => Object
    .keys(obj)
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]))
    .join('&');

function ImagePreview() {
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
function VideoPreview() {
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
                Video.time = e.target.currentTime
                Edl.time = Video.time + Edl.durations(Edl.edl.slice(0,Edl.current))
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
        if (Video.time < Edl.edl[Edl.current]['inpoint']) {
          console.log('jumping to inpoint')
          vnode.dom.currentTime = Video.time
        }
      })
    },
    view: (vnode) => {
      return m('video', {
        src: vnode.attrs.src,
        currentTime: Video.time,
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
          return m(ImagePreview, {
            id: 'preview',
            src: `otto/template/${clip['name']}?${urlfy(clip.data)}&t=${Video.time}`
          })
        } else {
            return m(VideoPreview, {
              id: 'preview',
              src: clip.filename
            })
        }
      }
    }
  }
})
