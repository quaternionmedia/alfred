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
                t: .5,
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
  // let start = 17.2
  // let duration = 7
  let start = 0
  let duration = 5
  return {
    // duration: 30,
    duration: 5,
    edl: [
      // {
      //   type: 'video',
      //   name: 'https://storage.googleapis.com/tower-bucket/alfred/car/Magnussens%20(check%20out%20offer).mp4',
      //   duration: 30,
      //   start: 0,
      // },
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
          color: '#FF0000',
          textsize: [1280,320],
          fontsize: 100,
          position: 'top',
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
        data: {
          color: '#000000',
          text: offer,
          textsize: [1600,720],
          fontsize: 50,
          opacity: 1,
          position: 'center',
          align: 'west',
          // duration: duration,
        },
      },
      {
        type: 'template',
        name: 'textBox',
        duration: duration,
        start: start,
        data: {
          color: '#555555',
          text: legal,
          textsize: [1800,400],
          fontsize: 25,
          position: 'bottom',
          align: 'west',
          opacity: 1,
          // duration: duration,
        },
      }
    ]
  }
}