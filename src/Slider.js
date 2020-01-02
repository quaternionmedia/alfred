import m from 'mithril'
import interact from 'interactjs'
var state = require("./Globals").state
import Monitor from './Monitor'
import Video from './Video'

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = ((Math.floor(seconds*100) % 6000)/100).toFixed(2);
  return [
    h,
    m > 9 ? m : (h ? '0' + m : m || '0'),
    s > 9 ? s : '0' + s,
  ].filter(a => a).join(':');
}

var sliderDom = {
  dom: null
}

module.exports = {
  v: null,
  view: (vnode) => {
    return m('.slider#slider', {min: 1, max: Video.duration, value: Video.time}, Video.time > 60 ? formatTime(Video.time.toFixed(2)): Video.time.toFixed(2))
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
        event.target.setAttribute('data-value', (value*Video.duration).toFixed(2))
        event.target.setAttribute('value', value*Video.duration)
        // state.time(value)
        Monitor.seek(value*Video.duration)
        // var t = document.getElementById('timeline')
        // t.style.transform = `scale(${value})`
    })
  },
  onupdate: (vnode) => {
    // console.log('updating slider', vnode)
    vnode.dom.style.paddingLeft = Video.time/Video.duration*vnode.dom.offsetWidth
  },
}
