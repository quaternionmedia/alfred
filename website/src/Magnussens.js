import m from 'mithril'
import { success, error, message } from 'alertifyjs'
import { ImagePreview } from './Preview'
import { Form, Text, TextBox, Button, Img, Selector} from './Components'
import { User } from './User'
import { auth } from './Login'
import { Fields, MagnussensFields } from './Form'

import 'regenerator-runtime/runtime'

import { LogicEngine } from 'json-logic-engine'

export const generateParams = params => {
  let res = ''
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) {
      value.forEach((v, i) => {
        res += key + '=' + v + '&'
      })
    } else {
      res += key + '=' + String(value) + '&'
    }
  }
  res = res.substring(0, res.length - 1)
  return res
  
}

export function Magnussens() {
  if (!User.loggedIn) m.route.set('/login?redirect=' + m.route.get())
  let project
  let fields = []
  let logic
  let preview
  let engine = new LogicEngine()
  engine.addMethod('floor', Math.floor)
  engine.addMethod('sqrt', Math.sqrt)
  
  return {
    oninit: vnode => {
      if (m.route.param('project')) {
        auth('/project/' + m.route.param('project')).then(res => {
          console.log('project', res)
          project = res
          fields = res['fields']
          logic = engine.build(res['logic'])
        })
      }
    },
    view: vnode => {
      return [
        m('h2', {}, m.route.param('project')),
        m(Form, {id: 'MagnussensForm'}, [
          m(Fields, {}, fields),
          m(Selector, { name: 'resolution', text: 'Resolution'}, [
            '1920x1080', '1600x900', '1280x720',
          ]),
          m(Selector, { name: 'quality', text: 'Quality'}, [
            'web', 'TV'
          ]),
          m(Text, { name: 'description', text: 'Desciption (optional)'}, ''),
          m(Button, { name: 'preview', value: 'preview', onclick: e => {
            e.preventDefault()
            
            let form = new FormData(document.getElementById('MagnussensForm'))
            let data = Object.fromEntries(form.entries())
            data.width = data.resolution.split('x')[0]
            data.height = data.resolution.split('x')[1]
            let edl = logic(data)
            // edl.shift()
            console.log('previewing ', edl, vnode.dom)
            auth('/otto/preview', {
              params: {
                t: edl[1]['start'] + 1,
                width: data.resolution.split('x')[0],
                height: data.resolution.split('x')[1]
              },
              method: 'post',
              body: { clips: edl },
            }).then(res => {
              console.log('preview available at', res)
              preview = res
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
            data.width = data.resolution.split('x')[0]
            data.height = data.resolution.split('x')[1]

            let edl = logic(data)
            let ffmpeg_params = data.quality == 'TV' ? ['-b:v', '25M', '-maxrate', '30M', '-bufsize', '20M'] : ['-b:v', '5M', '-minrate', '1M', '-maxrate', '10M', '-bufsize', '5M']
            console.log('saving form', e, edl, data, data, ffmpeg_params)
            
            let params = {
              project: m.route.param('project'),
              width: data.width,
              height: data.height,
              fps: 29.97,
              quality: data.quality,
              description: data.description,
              ffmpeg_params: ffmpeg_params,
            }
            auth(`/render?${generateParams(params)}`, {
              method: 'post',
              body: {clips: edl, duration: data.duration}
            }).then(e => {
              success('Rendering!')
              m.route.set('/renders')
            }).catch(e => {
              console.log('error rendering', e)
            })
          },
        },),
        // m(Progress),
        m(ImagePreview, {src: preview,})
      ]),
    ]
  }
}
}
