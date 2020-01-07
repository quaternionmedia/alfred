import m from 'mithril'
import interact from 'interactjs'
import { Video } from './Video'
var Timeline = require('./Timeline').Timeline
var state = require("./Globals").state

module.exports = {
  view: (vnode) => {
    return m('.slider#scale', {min: .01, max: 100, value: state.scale()}, state.scale())},
  oncreate: (vnode) => {
    const slider = interact(vnode.dom)
    slider.draggable({
        origin: 'self',
        inertia: true,
        modifiers: [
          interact.modifiers.restrict({
            restriction: 'self'
          })
        ]
      })
      .on('dragmove',  (event) => {
        const sliderWidth = interact.getElementRect(event.target.parentNode).width
        const value = (100*event.pageX / sliderWidth).toFixed(2)

        event.target.style.paddingLeft = value + '%'
        event.target.setAttribute('data-value', value)
        event.target.setAttribute('value', value)
        state.scale(value)
        m.redraw()
    })
  },
}
