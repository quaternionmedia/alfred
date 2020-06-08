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

export var OttoTimeline = {
  oninit: (vnode) => {
    m.request('/otto').then(e => {
      console.log('got otto', e)
      Edl.edl = e
    })
  },
  view: (vnode) => {
    return m('#timeline.timeline', [
      Edl.edl.map((c, i) => {
        return m(Template, c)
      })
    ])
  }
}
