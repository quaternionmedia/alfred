import m from 'mithril'
import interact from 'interactjs'
import { Video } from './Video'
var Timeline = require('./Timeline').Timeline
var state = require("./Globals").state

function logslider(position) {
  // position will be between 0 and 100
  var minp = 0;
  var maxp = 1;

  // The result should be between 100 an 10000000
  var minv = Math.log(.01);
  var maxv = Math.log(100);

  // calculate adjustment factor
  var scale = (maxv-minv) / (maxp-minp);

  return Math.exp(minv + scale*(position-minp));
}

module.exports = {
  view: (vnode) => {
    return m('.slider#scale', {min: .01, max: 100}, state.scale() < 0 ? '1/' + state.scale() : state.scale())
  },
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
        // const sliderWidth = interact.getElementRect(event.target.parentNode).width
        let sliderWidth = event.target.offsetWidth
        let p = event.pageX / sliderWidth
        event.target.style.paddingLeft = p*100 + '%'
        const value = logslider(p).toFixed(4)
        event.target.setAttribute('data-value', value)
        event.target.setAttribute('value', value)
        state.scale(value)
        m.redraw()
    })
  },
}