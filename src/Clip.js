import m from 'mithril'
import interact from 'interactjs'
// import Timeline from './Timeline'
var Timeline = require("./Timeline")
import Monitor from './Monitor'
import { Video, Edl } from './Video'
var state = require("./Globals").state

function whichAmI(e, p) {
  let c = p.children
  for (var i = 0; i < c.length; i++) {
    if (c[i] == e) {
      return i
    }
  }
  return false
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
  /*  Create an interactable object in order to resize the left and right edges of the clip.
  */
  oncreate(vnode) {
    const clip = interact(vnode.dom)
    clip.resizable({
      edges: {
        left: true,
        right: true,
      },
      cursorChecker: (action, interactable, element, interacting) => {
        if (state.tool() == 'trim') {
          if (action.edges.right) {
            return 'e-resize'
          } else if (action.edges.left) {
            return 'w-resize'
          }
        }}
      }
    )
    clip.on('resizemove', (event) => {
      // console.log('resizemove', event)
      let target = event.target
      // console.log('event: ', event) //event.delta.x, )
      const w = parseInt(target.style.width)
      const dx = Number((event.dx / state.scale()).toFixed(2))
      // console.log( w - (vnode.state.outpoint - vnode.state.inpoint), event.rect.width, vnode.state.outpoint, vnode.state.inpoint, w)
      if (state.tool() == 'trim') {
        if (event.edges.left && ( this.outpoint > this.inpoint + dx) && (this.inpoint + dx >= 0)) {
          // target.style.width  = event.rect.width + 'px';
          target.style.width = w - dx + 'px'
          this.inpoint = this.inpoint + dx
          target.setAttribute('inpoint', this.inpoint)
          // console.log('changing inpoint', vnode, event)
        } else if (event.edges.right && (this.outpoint + dx > this.inpoint)) {
          target.style.width  = w + dx + 'px';
          this.outpoint = this.outpoint + dx
          target.setAttribute('outpoint', this.outpoint)
          // console.log('changing outpoint', event.deltaRect, event)
        }
      Timeline.Timeline.updateEdl()
    }
    })
    var self = this
    clip.draggable({
      listeners: {
        start (e) {
          console.log('dragging clip', e)
        },
        move (e) {
          if (state.tool() == 'slip') {
            const dx = e.dx / state.scale()
            if (self.inpoint + e.dx > 0) {
              console.log('slipping', e, dx)
              self.inpoint += dx
              self.outpoint += dx
              Timeline.Timeline.updateEdl()
            } else {
              self.outpoint -= self.inpoint
              self.inpoint = 0
            }
          } else if (state.tool() == 'slide') {
              const dx = e.dx / state.scale()
              console.log('sliding', e, dx)
              if (self.pos) {
                Edl.edl[self.pos - 1][2] = Math.max(Edl.edl[self.pos - 1][2] + dx, 0)
              }
              if (Edl.edl.length - 1 > self.pos) {
                Edl.edl[self.pos + 1][1] += dx
              }
              Timeline.Timeline.loadEdl(Edl.edl)

            }
          },
        end (e) {
        }
      }
    })


    vnode.dom.addEventListener('mousedown', (e) => {
      let target = e.target
      const r = e.offsetX / e.target.offsetWidth
      const t = Number((r*(this.outpoint - this.inpoint) + this.inpoint).toFixed(2))
      // let i = this.pos
      let i = whichAmI(target, target.parentElement)
      console.log('clicked on clip', i, e, r, t)
      if (state.tool() == 'time') {
        Edl.current = i
        if (Video.filename != Edl.edl[Edl.current][0]) {
          Video.filename = Edl.edl[Edl.current][0]
          Monitor.load(Video.filename)
        }
        Monitor.seek(t)
        m.redraw()
      } else if (state.tool() == 'cut') {
          if ((this.inpoint < t) && (t < this.outpoint)) {
            console.log(this.inpoint, t, this.outpoint)
            var edl = Edl.edl
            var newClip = [edl[i][0], edl[i][1], edl[i][2],edl[i][3],edl[i][4]]
            console.log('old:', edl[i])
            // var newClip = Edl.edl[i]
            edl[i][2] = t
            this.outpoint = t
            edl[i][3] = Number((edl[i][2] - edl[i][1]).toFixed(2))
            newClip[1] = t
            console.log('cutting', edl[i], newClip)
            newClip[3] = newClip[2] - newClip[1]
            edl.splice(i+1, 0, newClip)
            // Edl.edl = edl
            console.log('new edl', Edl.edl)
            // m.redraw()
            Timeline.Timeline.loadEdl(edl)
            // Timeline.Timeline.updateEdl()
          }
        }
    }, true)

  }
  onupdate(vnode) {
    this.pos = whichAmI(vnode.dom, vnode.dom.parentElement)
    // console.log('updating clip pos', this.filename, this.pos)
  }
  view(vnode) {
    return m(`.clip#${vnode.attrs.name}`, {
      'data-x': this.inpoint, // /state.scale(),
      // 'data-duration': vnode.attrs.duration/scale,
      // innerHTML: `${this.description} - [${this.inpoint}, ${this.outpoint}]`,
      pos: this.pos,
      inpoint: this.inpoint,
      outpoint: this.outpoint,
      filename: this.filename,
      description: this.description,
      title: this.pos + ' - ' + this. filename + ' - ' + this.description,
      style: {
        width: (this.outpoint - this.inpoint)*state.scale(),
      },
    }, [
      m('p#clipname.clipname', this.filename.split('/').pop()),
      m('p#inpoint[]', this.inpoint.toFixed(2)),
      m('p#outpoint[]', this.outpoint.toFixed(2)),
      m('p#description[contenteditable=true]', {
        oncreate: (v) => {
          let t = document.getElementById('timeline')
          // console.log('description created', v)
          vnode.dom.addEventListener('input', (e) => {
            console.log('input changed', e, vnode, this.pos)
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
          display: (Edl.current == this.pos) && (this.inpoint < Video.time < this.outpoint) ? 'inherit': 'none',
          left: (Video.time - this.inpoint)*state.scale(),
        }
      }),
    ])
    // {data-x: vnode.attrs.inpoint/scale, data-y: vnode.attrs.outpoint/scale})
  }
}
