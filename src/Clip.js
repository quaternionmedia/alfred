import m from 'mithril'
import interact from 'interactjs'
// import Timeline from './Timeline'
var Timeline = require("./Timeline")
import Monitor from './Monitor'
import { Video, Edl } from './Video'

function whichAmI(e) {
  console.log('finding index of ', e)
  let c = e.parentElement.children
  for (var i = 0; i < c.length; i++) {
    if (c[i] == e.target) {
      return i
    }
  }
}

export default class Clip {
  constructor(vnode) {
    this.inpoint = vnode.attrs.inpoint
    this.outpoint = vnode.attrs.outpoint
    this.description = vnode.attrs.description
    this.filename = vnode.attrs.filename
    this.pos = vnode.attrs.pos
    // console.log('clip init', vnode, this.inpoint, this.outpoint)
    }

  oninit(vnode) {
  }
  oncreate(vnode) {
    const clip = interact(vnode.dom)
    clip.on('resizemove', (event) => {
      // console.log('resizemove', event)
      let target = event.target
    // console.log('event: ', event) //event.delta.x, )
    var w = parseInt(target.style.width)
    // console.log( w - (vnode.state.outpoint - vnode.state.inpoint), event.rect.width, vnode.state.outpoint, vnode.state.inpoint, w)
    if (event.edges.left && ( this.outpoint > this.inpoint + event.dx) && (this.inpoint + event.dx >= 0)) {
      // target.style.width  = event.rect.width + 'px';
      target.style.width = w - event.dx + 'px'
      this.inpoint += event.dx
      target.setAttribute('inpoint', this.inpoint)
      // console.log('changing inpoint', vnode, event)
    } else if (event.edges.right && (this.outpoint + event.dx > this.inpoint)) {
      target.style.width  = w + event.dx + 'px';
      this.outpoint += event.dx
      target.setAttribute('outpoint', this.outpoint)
      // console.log('changing outpoint', event.deltaRect, event)
    }
    Timeline.Timeline.updateEdl()
    })
    clip.resizable({
      edges: {
        left: true,
        right: true,
      }
    })
    // clip.on('resizestart', (event) => {
    //   state.resizing(true)
    //   console.log('resize start', state.resizing())
    // })
    // clip.on('resizeend', (event) => {
    //   state.resizing(false)
    //   console.log('resize stop', state.resizing())
    // })

    vnode.dom.addEventListener('mousedown', (e) => {
      // e.stopPropagation()
      const r = e.offsetX / e.target.offsetWidth
      const t = r*(this.outpoint - this.inpoint) + this.inpoint
      console.log('clicked on clip', e, r, t)
      Monitor.seek(t)
      Edl.current = whichAmI(e.target)
      m.redraw()
    }, true)

  }
  view(vnode) {
    return m(`.clip#${vnode.attrs.name}`, {
      'data-x': this.inpoint, // /state.scale(),
      // 'data-duration': vnode.attrs.duration/scale,
      // innerHTML: `${this.description} - [${this.inpoint}, ${this.outpoint}]`,
      inpoint: this.inpoint,
      outpoint: this.outpoint,
      filename: this.filename,
      description: this.description,
      pos: this.pos,
      style: {
        width: this.outpoint - this.inpoint,
      },
    }, [
      m('p#clipname.clipname', this.filename.split('/').pop()),
      m('p#inpoint[]', this.inpoint),
      m('p#outpoint[]', this.outpoint),
      m('p#description[contenteditable=true]', {
          oncreate: (v) => {
            // console.log('description created', v)
            vnode.dom.addEventListener('input', (e) => {
              console.log('input changed', e)
              Edl.edl[this.pos][4] = e.target.textContent
              this.description = e.target.textContent
            })
            vnode.dom.addEventListener('keyup', (e) => {
              if (e.key == 'Enter') {
                e.preventDefault()
                m.redraw()
              }
              if (e.key == 'ArrowLeft' || e.key == 'ArrowRight' || e.key == ' ') {
                e.stopPropagation()
              }
            })
          }
        }, m.trust(this.description)),
      m('i.material-icons#progress.progress',  {
        style: {
          display: (Video.time > this.inpoint) && (Video.time < this.outpoint) ? 'inherit': 'none',
          left: Video.time - this.inpoint,
        }
      }),
    ])
      // {data-x: vnode.attrs.inpoint/scale, data-y: vnode.attrs.outpoint/scale})
  }
}
