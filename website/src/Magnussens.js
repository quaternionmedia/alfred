import m from 'mithril'
import { success, error, message } from 'alertifyjs'
import { ImagePreview } from './Preview'
import { Form, TextBox, Button, Img, Selector} from './Components'
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
        m(Form, {id: 'MagnussensForm'}, [
          m(Fields, {}, fields),
          m(Selector, { name: 'resolution', text: 'Resolution'}, [
            '1920x1080', '1600x900', '1280x720',
          ]),
          m(Selector, { name: 'quality', text: 'Quality'}, [
            'web', 'TV'
          ]),
          m(Button, { name: 'preview', value: 'preview', onclick: e => {
            e.preventDefault()
            
            let form = new FormData(document.getElementById('MagnussensForm'))
            let data = Object.fromEntries(form.entries())
            data.project = 'Magnussens'
            data.width = data.resolution.split('x')[0]
            data.height = data.resolution.split('x')[1]
            data.textStart = data.duration == 15 ? 8 : 17.1
            data.textDuration = data.duration == 15 ? 5 : 7.2
            let edl = logic(data)
            edl.shift()
            console.log('previewing ', edl, vnode.dom)
            auth('/otto/preview', {
              params: {
                t: data.duration == 15 ? 10 : 20,
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
            data.project = 'Magnussens'
            data.width = data.resolution.split('x')[0]
            data.height = data.resolution.split('x')[1]
            data.textStart = data.duration == 15 ? 8 : 17.1
            data.textDuration = data.duration == 15 ? 5 : 7.2
            if (data.project == 'RSG') {
              data.textStart -= 2.7
              data.textDuration += 3.5
            }
            // let edl = buildEdl(data)
            // let edl = jsonLogic.apply(rules, data)
            let edl = logic(data)
            let ffmpeg_params = data.quality == 'TV' ? ['-b:v', '25M', '-maxrate', '30M', '-bufsize', '20M'] : ['-b:v', '5M', '-minrate', '1M', '-maxrate', '10M', '-bufsize', '5M']
            console.log('saving form', e, edl, data, data, ffmpeg_params)
            
            let params = {
              project: data.project,
              width: data.width,
              height: data.height,
              fps: 29.97,
              quality: data.quality,
              // bitrate: data.quality == 'TV' ? '20M' : '5M',
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
// 
// const rules = engine.build({merge: [
//   {eachKey: {
//     type: 'video',
//     name: {if: [ {'==': [{var: 'project'}, 'Magnussens']},
//     'https://storage.googleapis.com/tower-bucket/alfred/car/Magnussens%20(check%20out%20offer).mp4',
//     'https://storage.googleapis.com/tower-bucket/alfred/car/315048_MUL_MY21_MRE_RSG_LVStory_Downtown_Non-New_ENG_17-10-03_ProdAssetDlrNFA_SSSH2955000H.mp4',
//   ]},
//     duration: {var: 'duration'},
//     start: 0,
//     inpoint: {if: [ {'==': [{var: 'project'}, 'Magnussens']}, 0, 7]}
//   }},
//   {if: [ {'==': [{var: 'project'}, 'Magnussens']},
//     {eachKey: {
//       type: 'template',
//       name: 'makeColor',
//       duration: {var: 'textDuration'},
//       start: {var: 'textStart'},
//       data: {preserve: {
//         color: [255,255,255],
//         opacity: 1,
//       }}
//     }}
//   ]},
//   {eachKey: {
//     type: 'template',
//     name: 'textBox',
//     duration: {var: 'textDuration'},
//     start: {var: 'textStart'},
//     data: {eachKey: {
//       text: {var: 'carname'},
//       color: '#000000',
//       textsize: [{'floor':{'*':[.9, {var: 'width'}]}}, {'floor':{'*':[.3, {var: 'height'}]}}],
//       font: 'Toyota-Type-Bold',
//       fontsize: {'/': [{'sqrt': [{'*': [{var: 'width'}, {var: 'height'}]}]}, 15]},
//       position: ['center', {'floor': {'*': [.1, {var: 'height'}]}}],
//       opacity: 1,
//       fxs: [{preserve: {
//         name: 'bezier2',
//         data: {
//           c1x: 1,
//           c1y: 0,
//           ax: 0,
//           ay: 0,
//           c2x: 0,
//           c2y: 1,
//         }
//       }}]
//     }},
//   },},
//   {eachKey: {
//     type: 'template',
//     name: 'textBox',
//     duration: {var: 'textDuration'},
//     start: {var: 'textStart'},
//     position: [.5, .8 ],
//     data: {eachKey: {
//       color: '#EB0A1E',
//       text: {var: 'offerinfo'},
//       textsize: [{'floor':{'*':[.9, {var: 'width'}]}}, {'floor':{'*':[.5, {var: 'height'}]}}],
//       font: 'Toyota-Type',
//       fontsize: {'/': [{sqrt: {'*': [{var: 'width'}, {var: 'height'}]}}, 32]},
//       opacity: 1,
//       position: 'center',
//       align: {if: [{'==': [{var: 'offeralign'}, 'left']}, 'west', {var: 'offeralign'}]},
//     }},
//   }},
//   {eachKey: {
//     type: 'template',
//     name: 'textBox',
//     duration: {var: 'textDuration'},
//     start: {var: 'textStart'},
//     data: {eachKey: {
//       color: '#333333',
//       text: {var: 'legaltext'},
//       method: 'caption',
//       textsize: [{'floor':{'*':[.9, {var: 'width'}]}}, {'floor':{'*':[.35, {var: 'height'}]}}],
//       font: 'Toyota-Type-Book',
//       fontsize: {'/': [{sqrt: {'*': [{var: 'width'}, {var: 'height'}]}}, 60]},
//       position: ['center', 'bottom'],
//       align: 'west',
//       opacity: 1,
//     }}
//   }},
//   {if: [ {'==': [{var: 'project'}, 'Magnussens']},
//     {eachKey: {
//       type: 'image',
//       name: 'https://storage.googleapis.com/tower-bucket/alfred/car/magnussens-screengrab%20logo-fixed-with-toyota.png',
//       position: ['center', 'top'],
//       resize: {'/': [{sqrt: [{'*': [{var: 'width'}, {var: 'height'}]}]}, 3600]},
//       start: {var: 'textStart'},
//       duration: {var: 'textDuration'},
//     }}]}
// 
// ]})
