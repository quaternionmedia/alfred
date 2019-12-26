import m from 'mithril'
import interact from 'interactjs'
var state = require("./Globals").state
// var mon = require('./Monitor').Mon
import Monitor from './Monitor'
var Slider = {
  view: (vnode) => {
    return m('.slider#slider', {min: 1, max: 100})
  },
  oncreate: (vnode) => {
    const slider = interact('.slider')    // target elements with the "slider" class

    slider
      // Step 2
      .draggable({                        // make the element fire drag events
        origin: 'self',                   // (0, 0) will be the element's top-left
        inertia: true,                    // start inertial movement if thrown
        modifiers: [
          interact.modifiers.restrict({
            restriction: 'self'            // keep the drag coords within the element
          })
        ]
      })
      // Step 3
      .on('dragmove', function (event) {  // call this listener on every dragmove
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
