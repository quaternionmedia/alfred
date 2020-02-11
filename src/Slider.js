import m from 'mithril'
import interact from 'interactjs'
var state = require("./Globals").state
import Monitor from './Monitor'
import { Video, Edl } from './Video'

module.exports = {
  formatTime: (seconds) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = ((Math.floor(seconds*100) % 6000)/100).toFixed(2);
    return [
      h,
      m > 9 ? m : (h ? '0' + m : m || '0'),
      s > 9 ? s : '0' + s,
    ].filter(a => a).join(':');
  },
  elapsed: (e) => {
    let d = e.map(clip => clip[3])
    return d.reduce((a, b) => a + b, 0)
  },
  view: (vnode) => {
    return m('.slider#slider', {min: 1, max: Edl.duration(), value: Video.time}, Video.time > 60 ? module.exports.formatTime(Video.time.toFixed(2)): Video.time.toFixed(2))
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
        const sliderWidth = interact.getElementRect(event.target.parentNode).width
        const value = (event.pageX / sliderWidth).toFixed(2)

        event.target.style.paddingLeft = 100*value + '%'
        event.target.setAttribute('data-value', (value*Edl.duration()).toFixed(2))
        event.target.setAttribute('value', value*Edl.duration())
        Monitor.seekEdl(value*Edl.duration())
    })
  },
  onupdate: (vnode) => {
    let t = Video.time - Edl.edl[Edl.current][1] + module.exports.elapsed(Edl.edl.slice(0, Edl.current))
    // console.log('updating slider', vnode, t)
    vnode.dom.setAttribute('data-value', t.toFixed(2))
    vnode.dom.style.paddingLeft = t/Edl.duration()*vnode.dom.offsetWidth
  },
}
