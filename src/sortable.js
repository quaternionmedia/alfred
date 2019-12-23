import m from 'mithril'
import Sortable from 'sortablejs'

module.exports = {
  oncreate: (vnode) => {
    var sortable = Sortable.create(vnode.dom, {animation: 200})
  },
  view: (vnode) => {
    return m('.sortable', {width: '100%'}, [m('#1.clip', 1), m('#2.clip', 2), m('#3.clip', 3)])
  }
}
