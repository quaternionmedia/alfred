import m from 'mithril'
import { Video } from './Video'
var state = require("./Globals").state

export function Resolution() {
  return {
    view: (vnode) => {
      return m('select#resolution', {
        value: `${state.resolution()}p`,
        onchange: e => {
          let res = e.target.value.split('p')[0]
          state.resolution(res)
          console.log('changing resolution', res)
        },
        ...vnode.attrs,
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
      return m('select#aspect', {
        value: `${state.aspectWidth()}:${state.aspectHeight()}`,
        onchange: e => {
          let res = e.target.value.split(':')
          state.aspectWidth(res[0])
          state.aspectHeight(res[1])
          console.log('changing aspects', state.aspectWidth(), state.aspectHeight(), state.width(), state.height())
        },
        ...vnode.attrs,
      }, [
        vnode.children.map(opt => {
          return m('option', {value: opt}, opt)
        })
      ])

    }
  }
}
