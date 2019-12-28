import m from 'mithril'
import interact from 'interactjs'
var state = require("./Globals").state
import Monitor from './Monitor'

var Slider = {
  view: (vnode) => {
    return m('.slider#slider', {min: 1, max: state.duration()})
  },
  oncreate: (vnode) => {
    const slider = interact('.slider')
    slider.draggable({
        origin: 'self',
        inertia: true,
        modifiers: [
          interact.modifiers.restrict({
            restriction: 'self'
          })
        ]
      })
      .on('dragmove', function (event) {
        const sliderWidth = interact.getElementRect(event.target.parentNode).width
        const value = (100*event.pageX / sliderWidth).toFixed(2)

        event.target.style.paddingLeft = value + '%'
        event.target.setAttribute('data-value', value)
        event.target.setAttribute('value', value)
        state.time(value)
        Monitor.seek(value)
        // var t = document.getElementById('timeline')
        // t.style.transform = `scale(${value})`
    })
  },
}

module.exports = {
  view: (vnode) => {
    return [
      m(Slider)
    ]
  }
}
