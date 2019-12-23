import m from 'mithril'
import interact from 'interactjs'
// import dragula from 'dragula'
import Sortable from 'sortablejs'
var state = require("./Globals").state


var clips = 0
var p = {x: 0, y: 0}
var scale = 10

class Clip {
  constructor(vnode) {
    this.inpoint = vnode.attrs.inpoint
    this.outpoint = vnode.attrs.outpoint
    this.description = vnode.attrs.description
    console.log('clip init', vnode, this.inpoint, this.outpoint)
    }

  oninit(vnode) {
  }
  oncreate(vnode) {
    const clip = interact(vnode.dom)
    clip.on('resizemove', (event) => {
      state.resizing(true)
      let target = event.target
      target.style.width  = event.rect.width + 'px';
      // let { x, y } = event.target.dataset
      // var x = (parseFloat(target.getAttribute('data-x')) || 0)
      // var y = (parseFloat(target.getAttribute('data-y')) || 0)
      // console.log('x,y: ', x, y)

      // x += event.deltaRect.left;
      // target.style.webkitTransform = target.style.transform =
      //   `translate(${x}px,${y}px)`;

    // target.setAttribute('data-x', x);
    var midpoint = target.offsetLeft + target.offsetWidth / 2
    console.log('event: ', event) //event.delta.x, midpoint)
    if (event.page.x < midpoint) {
      vnode.state.inpoint += event.deltaRect.left
      console.log('changing inpoint', vnode)
    } else {
      vnode.state.outpoint += event.deltaRect.right
      console.log('changing outpoint', event.deltaRect, midpoint)
    }
    target.innerHTML= `${vnode.state.description} - [${vnode.state.inpoint}, ${vnode.state.outpoint}]`
    // m.redraw()
    })
    clip.resizable({
      edges: {
        left: true,
        right: true,
      }
    })
    clip.on('resizestart', (event) => {
      state.resizing(true)
      console.log('resize start', state.resizing())
    })
    clip.on('resizeend', (event) => {
      state.resizing(false)
      console.log('resize stop', state.resizing())
    })
  }
  view(vnode) {
    return m(`.clip#${vnode.attrs.name}`, {'data-x': vnode.state.inpoint/scale, 'data-duration': vnode.attrs.duration/scale, innerHTML: `${vnode.state.description} - [${vnode.state.inpoint}, ${vnode.state.outpoint}]`, inpoint: vnode.state.inpoint, outpoint: vnode.state.outpoint}, [
      // m('.handle lh', {onmousedown: this.initialiseResize}),
      // m('.handle rh', {onmousedown: this.initialiseResize})
    ])
      // {data-x: vnode.attrs.inpoint/scale, data-y: vnode.attrs.outpoint/scale})
  }
  // onupdate(vnode) {
  //   console.log('updating', vnode.attrs.inpoint, vnode.attrs.outpoint)
  //   vnode.dom.innerHTML= `${vnode.attrs.description} - [${vnode.attrs.inpoint}, ${vnode.attrs.outpoint}]`
  // }
}

var Timeline = {
  edl: [],
  oninit: (vnode) => {

  },
  oncreate: (vnode) => {
    new Sortable(vnode.dom, {
      swapThreshold: 0.50,
      animation: 150,
      // ghostClass: 'blue-background-class',
      ghostClass: 'ghost',
      forceFallback: true,
      // delay: 100,
      filter: (e) => {
        var cursor = e.target.style.cursor;
        console.log('filter: ', e, cursor)
        return cursor == 'ew-resize'
      }

    })
      m.request('/edl').then((e) => {
      Timeline.edl = e
      console.log(Timeline.edl)
    })

  },
  view: (vnode) => {
    return m('#timeline.timeline', [
      // m(Clip)
      Timeline.edl.map((c) => {
        return m(Clip, {name: c[0], inpoint: c[1], outpoint: c[2], duration: c[3], description: c[4]})

      })
    ])
  },
}

module.exports = {
  view: (vnode) => {
    return m(Timeline)
  }
}
