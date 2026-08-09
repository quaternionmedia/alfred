import m from 'mithril'
import interact from 'interactjs'
var state = require("./Globals").state
import { Video, Edl } from './Video'
import { Player } from './Player'

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
    return m('.slider#slider', {min: 1, max: Edl.duration()})
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
        const sliderWidth = event.target.offsetWidth - event.target.offsetLeft
        const value = Math.max((event.pageX - event.target.offsetLeft) / sliderWidth, 0)
        const t = (value*Edl.duration()).toFixed(2)
        console.log('sliding to', t, value, event, event.pageX, sliderWidth, event.target.offsetLeft)
        event.target.style.paddingLeft = 100*value.toFixed(4) + '%'
        event.target.setAttribute('data-value', t)
    })
    .on('dragend', (event) => {
      const sliderWidth = event.target.offsetWidth - event.target.offsetLeft
      const value = Math.max((event.pageX - event.target.offsetLeft) / sliderWidth, 0)
      const t = (value*Edl.duration()).toFixed(2)
      // Through the transport, so the video element follows the scrub rather
      // than staying where it was until the next clip boundary.
      Player.seek(Number(t))
    })
  },
  onupdate: (vnode) => {
    vnode.dom.setAttribute('data-value', Edl.time.toFixed(2))
    // Guarded: an empty timeline has zero duration, and 0/0 wrote
    // `padding-left: NaN%` on every redraw.
    const total = Edl.duration()
    const p = total > 0 ? (Edl.time / total) * 100 : 0
    vnode.dom.style.paddingLeft = `${p.toFixed(2)}%`
  },
}
