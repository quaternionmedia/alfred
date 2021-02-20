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

export function Magnussens() {
  let preview
  return {
    view: (vnode) => {
      return [
          m(Form, {id: 'MagnussensForm'}, [
          m(TextBox, { name: 'Car name' }),
          m(TextBox, { name: 'Offer info' }),
          m(TextBox, { name: 'Legal text' }),
          m(Button, { name: 'preview', value: 'preview', onclick: e => {
            let form = new FormData(document.getElementById('MagnussensForm'))
            let edl = buildEdl(form.get('Car name'), form.get('Offer info'), form.get('Legal text'))
            console.log('previewing ', edl, vnode.dom)
            m.request('/otto/preview', {
              params: { 
                t: 20,
                // width: window.innerWidth,
                // height: Math.floor(window.innerWidth*9/16)
              },
              method: 'post',
              body: edl,
            }).then(res => {
              console.log('preview available at', res)
              preview = res
              m.redraw()
            }).catch(e => {
              console.log('error previewing', e)
            })
          }},),
          m(Button, { name: 'save', type: 'submit', value: 'render',
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
              m.route.set('/renders')
            }).catch(e => {
              console.log('error rendering', e)
            })
          },
        },),
        m(Img, {src: preview, class: 'preview'})
      ]),
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

function buildEdl(car, offer, legal) {
  return {
    duration: 30,
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
          position: 'top'
        },
      },
      {
        type: 'template',
        name: 'initial',
        duration: 6,
        start: 17.5,
        data: {
          text: offer,
          clipsize: [1280,720],
        },
      },
      {
        type: 'template',
        name: 'initial',
        duration: 6,
        start: 17.5,
        data: {
          text: legal,
          clipsize: [1280,720],
          position: 'bottom'
        },
      }
    ]
  }
}