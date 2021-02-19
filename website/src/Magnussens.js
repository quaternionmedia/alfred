import m from 'mithril'
import { Menu } from './Menu'
import { success, error, message } from 'alertifyjs'

export function Form() {
  return {
    view: vnode => {
      return m('form', vnode.attrs, vnode.children)
    }
  }
}

export function TextBox() {
  return {
    view: vnode => {
      return [
        m('label.formlabel', {for: vnode.attrs.name}, vnode.attrs.name),
        m('textarea', vnode.attrs),
        m('br')
      ]
    }
  }
}
export function Button() {
  return {
    view: vnode => {
      return m('input.button', {type: 'submit', ...vnode.attrs}, vnode.children)
    }
  }
}

export function Magnussens() {
  return {
    view: (vnode) => {
      return [
        m(Menu),
        m(Form, {id: 'MagnussensForm'}, [
          m(TextBox, { name: 'Car name' }),
          m(TextBox, { name: 'Offer info' }),
          m(TextBox, { name: 'Legal text' }),
          m(Button, { name: 'save', value: 'render',
          onclick: e => {
            e.preventDefault()
            let form = new FormData(document.getElementById('MagnussensForm'))
            console.log('saving form', e, form)
            message('rendering!')
            m.request('/save', {
              method: 'post',
              params: {
                project: 'Magnussens'
              },
              body: form
            }).then(e => {
              // message('rendering!')
            })
          },
        },),
      ])]
    }
  }
}