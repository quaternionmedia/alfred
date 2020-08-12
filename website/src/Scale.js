import m from 'mithril'
import interact from 'interactjs'
import { Video } from './Video'
var Timeline = require('./Timeline').Timeline
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
      return m('.slider#scale', {min: 1, max: 100, style: {paddingLeft: `${inverseLog(state.scale())*100}%`, 'background-color': '#393939'}})
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
          let p = Math.max(event.pageX - event.target.offsetLeft, 0) / sliderWidth
          // event.target.style.paddingLeft = p*100 + '%'
          const value = logslider(p).toFixed(4)
          console.log('scale:', value, 'padding:', p)
          // event.target.setAttribute('data-value', value)
          state.scale(value)
          m.redraw()
      })
    },
  }
}

export function Scale() {
  return {
    view: vnode => {
      return m('.tools.toolbar', {style:{width: 'auto'}}, [
        m('i.material-icons', {
          onclick: e => {
            let s = logslider(Math.max(inverseLog(state.scale()) - .05, .01))
            state.scale(s)
            console.log('zooming out', s)
          }
        }, 'zoom_out'),
        m(ScaleBar),
        m('i.material-icons', {
          style: {position: 'absolute', right:0},
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
