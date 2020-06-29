import m from 'mithril'
import { Video } from './Video'
var state = require("./Globals").state

export function Resolution() {
  return {
    view: (vnode) => {
      return m('select', {
        ...vnode.attrs,
        onchange: e => {
          let res = e.target.value.split('p')[0]
          state.resolution(res)
          console.log('changing resolution', res)
        }
      }, [
        vnode.children.map(opt => {
          return m('option', {value: opt}, opt)
        })
      ])
    }
  }
}

export function Aspect() {
  return {
    view: (vnode) => {
      return m('select', {
        ...vnode.attrs,
        onchange: e => {
          let res = e.target.value.split(':')
          state.aspectWidth(res[0])
          state.aspectHeight(res[1])
          console.log('changing aspects', res, state.width(), state.height())
        }
      }, [
        vnode.children.map(opt => {
          return m('option', {value: opt}, opt)
        })
      ])

    }
  }
}
