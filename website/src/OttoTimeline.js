import m from 'mithril'
import { Sortable, MultiDrag } from 'sortablejs'
Sortable.mount(new MultiDrag());
// var Clip = require('./Clip').Clip
import Clip from './Clip'
var state = require("./Globals").state
import { Video, Edl } from './Video'
import Monitor from './Monitor'

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
