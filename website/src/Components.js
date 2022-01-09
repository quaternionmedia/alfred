import m from 'mithril'
import { Menu } from './Menu'

export function Form() {
  return {
    view: vnode => {
      return m('form', vnode.attrs, vnode.children)
    }
  }
}
export function Text() {
  return {
    view: vnode => {
      return [
        m('label.formlabel', {for: vnode.attrs.name}, vnode.attrs.text),
        m('input[type=text]', vnode.attrs),
        m('br')
      ]
    }
  }
}
export function Textarea() {
  return {
    view: vnode => {
      return [
        m('label.formlabel', {for: vnode.attrs.name}, vnode.attrs.text),
        m('textarea', vnode.attrs),
        m('br')
      ]
    }
  }
}
export function Button() {
  return {
    view: vnode => {
      return m('input.button', vnode.attrs, vnode.children)
    }
  }
}

export function Img() {
  return {
    view: vnode => {
      return m('img', vnode.attrs, vnode.children)
    }
  }
}

export function Selector() {
  return {
    view: vnode => {
      return [
        m('label.formlabel', { for: vnode.attrs.name }, vnode.attrs.text),
        m('select', vnode.attrs, vnode.children.map(c => {
          return m('option', {value: c}, c)
        })),
        m('br'),
      ]
    }
  }
}


export function Section() {
  return {
    view: vnode => {
      return m('section', vnode.attrs, vnode.children)
    }
  }
}

export function Layout() {
  return {
    view: vnode => {
      return [
        m(Menu),
        m(Section, vnode.attrs, vnode.children)
      ]
    }
  }
}

