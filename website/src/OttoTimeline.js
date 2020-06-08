import m from 'mithril'
import { Sortable, MultiDrag } from 'sortablejs'
Sortable.mount(new MultiDrag());
// var Clip = require('./Clip').Clip
import Clip from './Clip'
var state = require("./Globals").state
import { Video, Edl } from './Video'
import Monitor from './Monitor'

function array_move(arr, old_index, new_index) {
    while (old_index < 0) {
        old_index += arr.length;
    }
    while (new_index < 0) {
        new_index += arr.length;
    }
    if (new_index >= arr.length) {
        var k = new_index - arr.length + 1;
        while (k--) {
            arr.push(undefined);
        }
    }
    arr.splice(new_index, 0, arr.splice(old_index, 1)[0]);
    return arr
};


export function Template() {
  return {
    view: (vnode) => {
      return m('.clip', {
          style: {
            width: vnode.attrs.duration*state.scale()
          },
      }, `${vnode.attrs.name} ${JSON.stringify(vnode.attrs.data)}`)
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
          Edl.current = e.newIndex
          console.log('sorting update', e, Edl)
          // Timeline.updateEdl()
        },
        removeOnSpill: true,
        onSpill: e => {
          console.log('spilling', e)
          Edl.edl.splice(e.oldIndex, 1)
          // Timeline.loadEdl(Edl.edl)
      },
    })
  },
    view: (vnode) => {
      return m('#timeline.timeline', [
        Edl.edl.map((c, i) => {
          return m(Template, c)
        })
      ])
    },
  }
}
