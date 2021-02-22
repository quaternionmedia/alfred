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
            edl.edl.shift()
            console.log('previewing ', edl, vnode.dom)
            m.request('/otto/preview', {
              params: {
                t: 1,
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
  let start = 17.2
  let duration = 7
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
        name: 'makeColor',
        duration: duration,
        start: start,
        data: {
          size: [1920,1080],
          color: [255,255,255],
          opacity: 1,
        }
      },
      {
        type: 'template',
        name: 'textBox',
        duration: duration,
        start: start,
        data: {
          text: car,
          color: '#EB0A1E',
          textsize: [1280,320],
          fontsize: 100,
          // position: [.8, .5],
          position: ['center',150],
          opacity: 1,
          fxs: [{
            name: 'bezier2',
            data: {
              c1x: 1,
              c1y: 0,
              ax: 0,
              ay: 0,
              c2x: 0,
              c2y: 1,
            }
          }]
        },
      },
      {
        type: 'template',
        name: 'textBox',
        duration: duration,
        start: start,
        position: [.5, .8 ],
        data: {
          color: '#EB0A1E',
          text: offer,
          textsize: [1700,600],
          fontsize: 50,
          opacity: 1,
          position: 'center',
          align: 'west',
        },
      },
      {
        type: 'template',
        name: 'textBox',
        duration: duration,
        start: start,
        data: {
          color: '#333333',
          text: legal,
          textsize: [1800,400],
          fontsize: 25,
          position: 'bottom',
          align: 'west',
          opacity: 1,
        }
      },
      {
        type: 'image',
        name: 'https://storage.googleapis.com/tower-bucket/alfred/car/magnussens-screengrab%20logo-fixed-with-toyota.png',
        position: ['center', 'top'],
        resize: .4,
        start: start,
        duration: duration,
      }
    ]
  }
}