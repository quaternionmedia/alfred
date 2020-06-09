import m from 'mithril'
import { Sortable, MultiDrag } from 'sortablejs'
Sortable.mount(new MultiDrag());
// var Clip = require('./Clip').Clip
import Clip from './Clip'
var state = require("./Globals").state
import { Video, Edl } from './Video'
import Monitor from './Monitor'

function array_move(arr, old_index, new_index) {
    let element = arr[old_index];
    arr.splice(old_index, 1);
    arr.splice(new_index, 0, element);
    return arr
};


export function Template() {
  return {
    oncreate: (vnode) => {
      let element = vnode.dom
      let original_width = 0;
      let original_x = 0;
      let original_mouse_x = 0;

      element.addEventListener('mousedown', e => {
        if (state.tool() == 'trim') {
          e.preventDefault()
          original_width = parseFloat(getComputedStyle(element, null).getPropertyValue('width').replace('px', ''));
          original_x = element.getBoundingClientRect().left;
          original_mouse_x = e.pageX;

          function resize(e) {
              const w = original_width + (e.pageX - original_mouse_x);
              const dx = e.movementX / state.scale()
              if ((w + dx) > 0)
              element.style.width = w + dx + 'px'
              console.log('trimmed', e, dx, element)
          }
          function stopResize() {
            element.removeEventListener('mousemove', resize)
            Edl.edl[vnode.attrs.i]['duration'] = parseFloat(element.style.width) / state.scale()
            m.redraw.sync()
          }

          element.addEventListener('mousemove', resize)
          element.addEventListener('mouseup', stopResize)

      })

    },
    view: (vnode) => {
      return m('.clip', {
          style: {
            width: vnode.attrs.duration*state.scale()
          },
      }, `${vnode.attrs.i} ${vnode.attrs.name} ${JSON.stringify(vnode.attrs.data)}`)
    }
  }
}

export function OttoTimeline() {
  return {
    oninit: (vnode) => {
      m.request('/otto').then(e => {
        console.log('got otto', e)
        Edl.edl = e
      })
    },
    oncreate: (vnode) => {
      new Sortable(vnode.dom, {
        multiDrag: true,
        group: 'media',
        selectedClass: "selected",
        swapThreshold: 0.50,
        animation: 150,
        ghostClass: 'ghost',
        forceFallback: true,
        // delay: 100,
        invertSwap: true,
        preventOnFilter: false,
        filter: (e) => {
           if (state.tool() != 'move') {
             return true
           }
           else {
             return false
           }
        },
        onUpdate: (e) => {
          Edl.edl = array_move(Edl.edl, e.oldIndex, e.newIndex)
          Edl.update()
          console.log('sorting update', e, Edl.edl)
        },
        removeOnSpill: true,
        onSpill: e => {
          console.log('spilling', e)
          Edl.edl.splice(e.oldIndex, 1)
          Edl.update()
      },
    })
  },
    view: (vnode) => {
      return m('#timeline.timeline', [
        Edl.edl.map((c, i) => {
          if (c) {
            c.i = i
            return m(Template, c)
          } else return m('')
        })
      ])
    },
  }
}
