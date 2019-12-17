import m from 'mithril'
import interact from 'interactjs'
import dragula from 'dragula'
var state = require("./Globals").state

var clips = 0
var p = {x: 0, y: 0}
var scale = 10
var dragOpts = {
  moves: (el, source, handle, sibling) => {
    return !state.resizing()
    // return false
  }
}

var Clip = {
  oninit: (vnode) => {
  },
  oncreate: (vnode) => {
    // vnode.state.inpoint =
  },
  view: (vnode) => {
    return m(`.clip#${vnode.attrs.name}`, {'data-x': vnode.attrs.inpoint/scale, 'data-duration': vnode.attrs.duration/scale}, vnode.attrs.description)
      // {data-x: vnode.attrs.inpoint/scale, data-y: vnode.attrs.outpoint/scale})
  }
}

var Timeline = {
  edl: [],
  oninit: (vnode) => {
    const clip = interact('.clip')

    // clip.draggable({
    //   inertia: true,
    //   // lockAxis: 'x',
    //   modifiers: [
    //     interact.modifiers.restrictRect({
    //       restriction: 'parent',
    //       endOnly: true,
    //     })
    //   ],
    //   autoscroll: true,
    //   listeners: {
    //     move: (event) => {
    //       let target = event.target
    //       var x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx
    //       var y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy
    //       // p.x += event.dx
    //       // p.y += event.dy
    //       target.style.webkitTransform = target.style.transform = `translate(${x}px,${y}px)`
    //       target.setAttribute('data-x', x)
    //       target.setAttribute('data-y', y)
    //     }
    //   },
    // })

    clip.on('resizemove', (event) => {

      let target = event.target
      // let { x, y } = event.target.dataset
      var x = (parseFloat(target.getAttribute('data-x')) || 0)
      // var y = (parseFloat(target.getAttribute('data-y')) || 0)
      // console.log('x,y: ', x, y)

      target.style.width  = event.rect.width + 'px';
      x += event.deltaRect.left;
      // target.style.webkitTransform = target.style.transform =
      //   'translate(' + x + 'px)';

    target.setAttribute('data-x', x);
    // target.textContent = `${event.rect.width}×${event.rect.height}\nx: ${x}\ny: ${y}`;
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

  },
  oncreate: (vnode) => {
    dragula([vnode.dom], dragOpts)
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
