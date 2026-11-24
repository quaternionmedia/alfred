import m from 'mithril'
import interact from 'interactjs'
import { Video } from './Video'
var state = require("./Globals").state

// position will be between 0 and 1
var minp = 0;
var maxp = 1;

// The result should be between .1 an 1000
var minv = Math.log(.1);
var maxv = Math.log(1000);

// calculate adjustment factor
var scale = (maxv-minv) / (maxp-minp);

export function logslider(position) {

  return Math.exp( minv + scale * ( position - minp ) );
}

export function inverseLog(value) {
  return ( ( Math.log(value) - minv ) / scale ) + minp
}

export function ScaleBar() {
  return {
    view: (vnode) => {
      // Where the thumb is, as a fraction of the bar (editor.scss draws it).
      // It was a `padding-left` percentage, which is of the toolbar's width,
      // not the bar's: the thumb ran past the bar's end.
      const at = Math.min(1, Math.max(0, inverseLog(state.scale())))
      return m('.slider#scale', {min: 1, max: 100, style: {'--at': at, 'background-color': '#393939'}})
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
          // Measured on the bar's own box, as the transport's bar is
          // (Slider.js): `pageX` less `offsetLeft` mixed the page's origin
          // with the nearest positioned ancestor's, and the timeline's tools
          // sit in one (`position: sticky`), as does every workspace panel.
          const box = event.target.getBoundingClientRect()
          const p = box.width > 0 ? Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)) : 0
          const value = logslider(p).toFixed(4)
          state.scale(value)
          m.redraw()
      })
    },
  }
}

export function Scale() {
  return {
    view: vnode => {
      return m('.tools.toolbar.zoombar', {style:{width: 'auto'}}, [
        m('i.material-icons', {
          onclick: e => {
            let s = logslider(Math.max(inverseLog(state.scale()) - .05, .01))
            state.scale(s)
            console.log('zooming out', s)
          }
        }, 'zoom_out'),
        m(ScaleBar),
        m('i.material-icons', {
          onclick: e => {
            let s = logslider(inverseLog(state.scale()) + .05)
            state.scale(s)
            console.log('zooming in', s)
          }
        }, 'zoom_in'),
      ])
    }
  }

}
