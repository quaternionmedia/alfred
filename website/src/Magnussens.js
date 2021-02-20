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
            // form.forEach(f => {console.log('field', f.name, f)})
            message('assembling render')
            let edl = buildEdl(form.get('Car name'), form.get('Offer info'), form.get('Legal text'))
            console.log('saving form', e, edl, form)
            
            
            m.request('/render', {
              method: 'post',
              params: {
                project: 'Magnussens'
              },
              body: edl
            }).then(e => {
              success('Rendering!')
            })
          },
        },),
      ])]
    }
  }
}

function buildEdl(car, offer, legal) {
  return {
    time: 30,
    edl: [
      {
        type: 'video',
        name: 'https://storage.googleapis.com/tower-bucket/alfred/car/Magnussens%20(check%20out%20offer).mp4',
        duration: 30,
        start: 0,
      },
      {
        type: 'template',
        name: 'title',
        duration: 6,
        start: 17.5,
        data: {
          text: car,
          clipsize: [1280,720],
        },
      }
    ]
  }
}