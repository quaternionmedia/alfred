import m from 'mithril'
import interact from 'interactjs'
var state = require("./Globals").state
import { Video, Edl } from './Video'
import { Player } from './Player'

/**
 * Where along a bar the pointer is, from 0 to 1, measured on the bar's own box.
 *
 * It was `pageX` less `offsetLeft`: one measured from the page, the other
 * from the nearest positioned ancestor, which agree only while the bar sits
 * in no positioned box. A workspace panel is one, and a scrub landed as far
 * from the pointer as the panel was from the page's edge. The zoom bar
 * (Scale.js) measures the same way.
 */
const along = event => {
  const box = event.target.getBoundingClientRect()
  if (!(box.width > 0)) return 0
  return Math.min(1, Math.max(0, (event.clientX - box.left) / box.width))
}

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
        const value = along(event)
        const t = (value*Edl.duration()).toFixed(2)
        event.target.style.paddingLeft = 100*value.toFixed(4) + '%'
        event.target.setAttribute('data-value', t)
    })
    .on('dragend', (event) => {
      const value = along(event)
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
