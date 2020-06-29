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
          let res = e.target.value.split('p')[0]
          state.resolution(res)
          console.log('res change', res, state.resolution())
          if (state.width() > state.height()) {
            state.width(state.resolution())
            state.height(parseInt(state.resolution()*state.aspectHeight()/state.aspectWidth()))
          } else {
            state.height(state.resolution())
            state.width(parseInt(state.resolution()*state.aspectWidth()/state.aspectHeight()))
          }
          if (state.width() % 2 != 0) state.width(state.width() - 1)
          if (state.height() % 2 != 0) state.width(state.height() - 1)
          console.log('res', state.width(), state.height(), state.aspectWidth(), state.aspectHeight())

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
          console.log('changing resolutions', e.target.value)
          let res = e.target.value.split(':')
          state.aspectWidth(res[0])
          state.aspectHeight(res[1])
          if (state.aspectWidth() > state.aspectHeight()) {
            state.height(state.resolution())
            state.width(parseInt(state.resolution()*state.aspectWidth()/state.aspectHeight()))
          } else {
            state.width(state.resolution())
            state.height(parseInt(state.resolution()*state.aspectHeight()/state.aspectWidth()))
          }
          if (state.width() % 2 != 0) state.width(state.width() - 1)
          if (state.height() % 2 != 0) state.width(state.height() - 1)
          console.log('res', state.width(), state.height(), state.aspectWidth(), state.aspectHeight())
        }
      }, [
        vnode.children.map(opt => {
          return m('option', {value: opt}, opt)
        })
      ])
    }
  }
}
