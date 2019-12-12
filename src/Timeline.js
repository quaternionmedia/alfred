import m from 'mithril'
import interact from 'interactjs'

var clips = 0
var p = {x: 0, y: 0}

var Clip = {
  oncreate: (vnode) => {
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
          var target = event.target
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
      let { x, y } = event.target.dataset
      x = parseFloat(x) || 0
      y = parseFloat(y) || 0
      Object.assign(event.target.style, {
        width: `${event.rect.width}px`,
        height: `${event.rect.height}px`,
        transform: `translate(${event.deltaRect.left}px, ${event.deltaRect.top}px)`
      })

      Object.assign(event.target.dataset, { x, y })
    })
    clip.resizable({
      edges: {
        left: true,
        right: true,
      }
    })
  },
  view: (vnode) => {
    return m('.clip', 'clip' + clips++)
  }
}

var Timeline = {

  view: (vnode) => {
    return m('#timeline', [
      m(Clip)
    ])
  }
}

module.exports = {
  view: (vnode) => {
    return m(Timeline)
  }
}
