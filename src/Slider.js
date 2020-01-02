import m from 'mithril'
import interact from 'interactjs'
var state = require("./Globals").state
import Monitor from './Monitor'
import Video from './Video'

var sliderDom = {
  dom: null
}

module.exports = {
  v: null,
  view: (vnode) => {
    return m('.slider#slider', {min: 1, max: state.duration(), value: Video.time}, Video.time)
  },
  updateValue: (value) => {
    if (sliderDom.dom) {
      sliderDom.dom.value = value
    }
    // m.redraw()
  },
  oncreate: (vnode) => {
    // this.value = vnode.attrs.value
    sliderDom = vnode.dom
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
      .on('dragmove',  (event) => {
        const sliderWidth = interact.getElementRect(event.target.parentNode).width
        const value = (event.pageX / sliderWidth).toFixed(2)

        event.target.style.paddingLeft = 100*value + '%'
        // event.target.setAttribute('data-value', value)
        event.target.setAttribute('value', value*Video.duration)
        // state.time(value)
        Monitor.seek(value*Video.duration)
        // var t = document.getElementById('timeline')
        // t.style.transform = `scale(${value})`
    })
  },
  onupdate: (vnode) => {
    console.log('updating slider', vnode)
    vnode.dom.style.paddingLeft = Video.time/Video.duration*vnode.dom.offsetWidth
  },
}
