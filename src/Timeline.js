import m from 'mithril'
import interact from 'interactjs'

var clips = 0
var p = {x: 0, y: 0}

var Clip = {
  edl: [],
  oninit: (vnode) => {
  },
  oncreate: (vnode) => {
    // vnode.state.inpoint =
  },
  view: (vnode) => {
    return m('.clip', 'clip' + clips++)
  }
}

var Timeline = {
  edl: [],
  oninit: (vnode) => {
    const clip = interact('.clip')
    clip.draggable({
      inertia: true,
      // lockAxis: 'x',
      modifiers: [
        interact.modifiers.restrictRect({
          restriction: 'parent',
          endOnly: true,
        })
      ],
      autoscroll: true,
      listeners: {
        move: (event) => {
          let target = event.target
          var x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx
          var y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy
          // p.x += event.dx
          // p.y += event.dy
          target.style.webkitTransform = target.style.transform = `translate(${x}px,${y}px)`
          target.setAttribute('data-x', x)
          target.setAttribute('data-y', y)
        }
      },
    })
    clip.on('resizemove', (event) => {
      let target = event.target
      // let { x, y } = event.target.dataset
      var x = (parseFloat(target.getAttribute('data-x')) || 0)
      var y = (parseFloat(target.getAttribute('data-y')) || 0)
      // console.log('x,y: ', x, y)

      target.style.width  = event.rect.width + 'px';
      x += event.deltaRect.left;
      target.style.webkitTransform = target.style.transform =
        'translate(' + x + 'px,' + y + 'px)';

    target.setAttribute('data-x', x);
    target.textContent = event.rect.width + '×' + event.rect.height;
    })
    clip.resizable({
      edges: {
        left: true,
        right: true,
      }
    })

  },
  oncreate: (vnode) => {
      m.request('/edl').then((e) => {
      Timeline.edl = e
      console.log(Timeline.edl)
    })

  },
  view: (vnode) => {
    return m('#timeline', [
      // m(Clip)
      Timeline.edl.map((c) => {
        return m(Clip, c)

      })
    ])
  },
}

module.exports = {
  view: (vnode) => {
    return m(Timeline)
  }
}
