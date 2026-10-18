import m from 'mithril'
import { success, error, message } from 'alertifyjs'
import { AuthedImage } from './Preview'
import { isSigned } from './Signed'
import { Form, Text, TextBox, Button, Img, Selector} from './Components'
import { User } from './User'
import { auth } from './Login'
import { Fields, MagnussensFields } from './Form'
import './timerange.css'
import 'regenerator-runtime/runtime'
import "../node_modules/mithril-range/index.css"
import range from 'mithril-range'

import { LogicEngine } from 'json-logic-engine'
import { layeredEdl, queueRender } from './RenderRequest'
import { escapeHtml, requestProblem } from './Problem'

// Named encoding presets the server applies; the first is the default.
const QUALITIES = ['standard', 'high', 'draft']

/**
 * The frame `POST /preview/` made, shown.
 *
 * The route answers with where the frame is. That was a path under the public
 * `/data` mount (`data/<uuid>.jpg`), which any `<img>` can show and so can
 * anyone else who learns the name; it is now a signed URL for the private
 * frames route (contract M1), which an `<img>` can show for a few minutes and
 * nobody can guess. Both are handed to the image as they are. A private path
 * that arrives unsigned is fetched with the session instead, since the image
 * alone would be refused.
 */
const FramePreview = {
  view: ({ attrs: { frame } }) => {
    const src = typeof frame === 'string' ? frame.replace(/^"|"$/g, '') : ''
    if (!src) return null
    if (isSigned(src) || /^https?:\/\//i.test(src)) return m('img.preview#form-preview', { src })
    if (/^\/?data\//.test(src)) {
      return m('img.preview#form-preview', { src: src.startsWith('/') ? src : `/${src}` })
    }
    return m(AuthedImage, { id: 'form-preview', src: src.startsWith('/') ? src : `/${src}` })
  },
}

/** The form's values, with the chosen resolution as numbers. */
function formData() {
  const data = Object.fromEntries(new FormData(document.getElementById('template_form')).entries())
  const [width, height] = String(data.resolution || '1920x1080').split('x').map(Number)
  return { ...data, width, height }
}

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
          // The server's quality presets. This offered "web" and "TV" and
          // sent ffmpeg flags of its own for each -- the server now chooses
          // the encoding from a named preset and refuses client-supplied
          // ffmpeg parameters, so a render from this form would have been
          // turned away.
          m(Selector, { name: 'quality', text: 'Quality'}, QUALITIES),
          m(Text, { name: 'description', text: 'Desciption (optional)'}, ''),
          m(Button, { name: 'preview', value: 'preview', onclick: e => {
            e.preventDefault()
            if (!logic) return error('This project has no logic to build a video from', 4)
            const data = formData()
            loading = true
            // The same placement rules as a render, so the frame previewed
            // is a frame of the video that will be made.
            auth('/preview/', {
              method: 'post',
              params: { t },
              body: {
                edl: layeredEdl(logic(data)),
                width: data.width,
                height: data.height,
              },
            }).then(res => {
              loading = false
              preview = res
            }).catch(err => {
              loading = false
              const why = requestProblem(err)
              error(why ? `Could not preview: ${escapeHtml(why)}` : 'Could not preview', 8)
            })
          }},),
          m(Button, { name: 'save', type: 'submit', value: 'render',
          onclick: e => {
            e.preventDefault()
            if (!logic) return error('This project has no logic to build a video from', 4)
            const data = formData()
            const edl = layeredEdl(logic(data))
            // The form's own length, when it has one, is the video's.
            const duration = Number(data.duration) || edl.duration
            edl.duration = duration
            message('assembling render')
            queueRender({
              edl,
              name: project.name,
              project: project.name,
              project_id: m.route.param('project'),
              description: data.description || undefined,
              width: data.width,
              height: data.height,
              fps: 29.97,
              quality: data.quality,
              duration,
            }).then(() => {
              success('Rendering!')
              // Into the flow, with the project, where the render is
              // followed until it finishes. This went to the retired
              // `/renders` route, which dropped the project.
              m.route.set('/', { stage: 'deliver', project: m.route.param('project') })
            }).catch(err => {
              // It failed silently: the reason went to the console.
              const why = requestProblem(err)
              error(
                why ? `Could not queue the render: ${escapeHtml(why)}` : 'Could not queue the render',
                8
              )
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
        loading ? m('.loader') : m(FramePreview, { frame: preview })
      ]),
    ]
  }
}
}
