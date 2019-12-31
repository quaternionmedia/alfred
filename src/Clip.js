import m from 'mithril'
import interact from 'interactjs'
// import Timeline from './Timeline'
var Timeline = require("./Timeline")

export default class Clip {
  constructor(vnode) {
    this.inpoint = vnode.attrs.inpoint
    this.outpoint = vnode.attrs.outpoint
    this.description = vnode.attrs.description
    this.filename = vnode.attrs.filename
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
    target.innerHTML= `${this.description} - [${this.inpoint}, ${this.outpoint}]`
    // m.redraw()
    // console.log('redrawing edl', Timeline.Timeline)
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
  }
  view(vnode) {
    return m(`.clip#${vnode.attrs.name}`, {
      'data-x': this.inpoint, // /state.scale(),
      // 'data-duration': vnode.attrs.duration/scale,
      innerHTML: `${this.description} - [${this.inpoint}, ${this.outpoint}]`,
      inpoint: this.inpoint,
      outpoint: this.outpoint,
      filename: this.filename,
      description: this.description,
      style: {
        width: this.outpoint - this.inpoint,
      },
      }, [
      ])
      // {data-x: vnode.attrs.inpoint/scale, data-y: vnode.attrs.outpoint/scale})
  }
}
