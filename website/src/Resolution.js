import m from 'mithril'
import { Video } from './Video'
var state = require("./Globals").state

export function Resolution() {
  return {
    view: (vnode) => {
      return m('select', {
        ...vnode.attrs,
        onchange: e => {
          console.log('changing resolutions', e.target.value)
          let res = e.target.value.split('x')
          state.width(res[0])
          state.height(res[1])
        }
      }, [
        vnode.children.map(opt => {
          return m('option', {value: opt}, opt)
        })
      ])
    }
  }
}
