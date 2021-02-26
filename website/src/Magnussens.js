import m from 'mithril'
import { Menu } from './Menu'
import { success, error, message } from 'alertifyjs'
import { ImagePreview } from './Preview'

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

export function Magnussens() {
  let preview
  return {
    view: (vnode) => {
      return [
        m(Form, {id: 'MagnussensForm'}, [
          m(Selector, { name: 'duration', text: 'Duration', value: 30 }, ['15', '30']),
          m(TextBox, { name: 'carname', text: 'Car Name' }),
          m(TextBox, { name: 'offerinfo', text: 'Offer Info' }),
          m(TextBox, { name: 'legaltext', text: 'Legal Text' }),
          m(Selector, { name: 'resolution', text: 'Resolution'}, ['1920x1080', '1280x720']),
          m(Button, { name: 'preview', value: 'preview', onclick: e => {
            let form = new FormData(document.getElementById('MagnussensForm'))
            let data = Object.fromEntries(form.entries())
            let edl = buildEdl(data)
            edl.edl.shift()
            console.log('previewing ', edl, vnode.dom)
            m.request('/otto/preview', {
              params: {
                t: 20,
                width: data.resolution.split('x')[0],
                height: data.resolution.split('x')[1]
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
            let data = Object.fromEntries(form.entries())
            let edl = buildEdl(data)
            console.log('saving form', e, edl, data, data.carname)
            
            
            m.request('/render', {
              method: 'post',
              params: {
                project: 'Magnussens',
                width: data.resolution.split('x')[0],
                height: data.resolution.split('x')[1]
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
        m(ImagePreview, {src: preview,})
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

function buildEdl(data) {
  let start = data.duration == 15 ? 8 : 17.2
  let duration = data.duration == 15 ? 5 : 7
  return {
    duration: data.duration,
    edl: [
      {
        type: 'video',
        name: 'https://storage.googleapis.com/tower-bucket/alfred/car/Magnussens%20(check%20out%20offer).mp4',
        duration: data.duration,
        start: 0,
      },
      {
        type: 'template',
        name: 'makeColor',
        duration: duration,
        start: start,
        data: {
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
          text: data.carname,
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
          text: data.offerinfo,
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
          text: data.legaltext,
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