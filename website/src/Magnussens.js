import m from 'mithril'
import { success, error, message } from 'alertifyjs'
import { ImagePreview } from './Preview'
import { Form, Text, TextBox, Button, Img, Selector} from './Components'
import { User } from './User'
import { auth } from './Login'
import { Fields, MagnussensFields } from './Form'
import './timerange.css'
import 'regenerator-runtime/runtime'
import "../node_modules/mithril-range/index.css"
import range from 'mithril-range'

import { LogicEngine } from 'json-logic-engine'

export function Magnussens() {
  let project
  let fields = []
  let logic
  let preview
  let loading = false
  let engine = new LogicEngine()
  let t = 1
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
        m('h2', {}, project ? project.name : ''),
        m(Form, {id: 'template_form'}, [
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
            loading = true

            let form = new FormData(document.getElementById('template_form'))
            let data = Object.fromEntries(form.entries())
            data.width = data.resolution.split('x')[0]
            data.height = data.resolution.split('x')[1]
            let edl = logic(data)
            // edl.shift()
            console.log('previewing ', edl, vnode.dom)
            auth('/preview/', {
              method: 'post',
              params: {
                  t: t
              },
              body: {
                edl: {clips: edl},
              },
            }).then(res => {
              console.log('preview available at', res)
              loading = false
              preview = res
            }).catch(e => {
              console.log('error previewing', e)
            })
          }},),
          m(Button, { name: 'save', type: 'submit', value: 'render',
          onclick: e => {
            e.preventDefault()
            let form = new FormData(document.getElementById('template_form'))
            // form.forEach(f => {console.log('field', f.name, f)})
            message('assembling render')
            let data = Object.fromEntries(form.entries())
            data.width = data.resolution.split('x')[0]
            data.height = data.resolution.split('x')[1]

            let edl = {clips: logic(data), duration: data.duration}
            let ffmpeg_params = data.quality == 'TV' ? ['-b:v', '25M', '-maxrate', '30M', '-bufsize', '20M'] : ['-b:v', '5M', '-minrate', '1M', '-maxrate', '10M', '-bufsize', '5M']
            console.log('saving form', e, edl, data, data, ffmpeg_params)
            
            let params = {
              project: project.name,
              project_id: m.route.param('project'),
              width: data.width,
              height: data.height,
              fps: 29.97,
              quality: data.quality,
              description: data.description,
              ffmpeg_params: ffmpeg_params,
              edl: edl,
              duration: data.duration ? data.duration : edl.duration,
            }
            auth(`/render`, {
              method: 'post',
              body: params
            }).then(e => {
              success('Rendering!')
              m.route.set('/renders')
            }).catch(e => {
              console.log('error rendering', e)
            })
          },
        },),
        // m(Progress),
        m(range, {
          min: 0,
          max: 30,
          step: .1,
          value: t,
          class: 'timerange',
          ondrag: v => {
            t = v.toFixed(1)
          }
        }, m('.timerange-value', {}, t)),
        loading ? m('.loader') : m(ImagePreview, {src: preview,})
      ]),
    ]
  }
}
}
