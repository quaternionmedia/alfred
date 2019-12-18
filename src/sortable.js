import m from 'mithril'
import Sortable from 'sortablejs'

module.exports = {
  oncreate: (vnode) => {
    var sortable = Sortable.create(vnode.dom)
  },
  view: (vnode) => {
    return m('.sortable', [m('#1', 1), m('#2', 2), m('#3', 3)])
  }
}
