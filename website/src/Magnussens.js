import m from 'mithril'
import { success, error, message } from 'alertifyjs'
import { ImagePreview } from './Preview'
import { Form, TextBox, Button, Img, Selector} from './Components'
import { User } from './User'
import { auth } from './Login'

export function Magnussens() {
  if (!User.loggedIn) m.route.set('/login?redirect=' + m.route.get())
  
  let preview
  return {
    view: (vnode) => {
      return [
        m(Form, {id: 'MagnussensForm'}, [
          // m(Selector, { name: 'project', text: 'Video', }, [ 'Magnussens', 'RSG']),
          m(Selector, { name: 'duration', text: 'Duration',}, ['30', '15']),
          m(TextBox, { name: 'carname', text: 'Car Name' }),
          m(TextBox, { name: 'offerinfo', text: 'Offer Info' }),
          m(Selector, { name: 'offeralign', text: 'Offer alignment' }, ['left', 'center']),
          m(TextBox, { name: 'legaltext', text: 'Legal Text' }),
          m(Selector, { name: 'resolution', text: 'Resolution'}, [
            '1920x1080', '1600x900', '1280x720', '854x480',
          ]),
          m(Button, { name: 'preview', value: 'preview', onclick: e => {
            e.preventDefault()
            let form = new FormData(document.getElementById('MagnussensForm'))
            let data = Object.fromEntries(form.entries())
            let width = data.resolution.split('x')[0]
            let height = data.resolution.split('x')[1]
            let edl = buildEdl(data, width, height)
            edl.shift()
            console.log('previewing ', edl, vnode.dom)
            auth('/otto/preview', {
              params: {
                t: data.duration == 15 ? 10 : 20,
                width: data.resolution.split('x')[0],
                height: data.resolution.split('x')[1]
              },
              method: 'post',
              body: { edl: edl },
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
            let width = data.resolution.split('x')[0]
            let height = data.resolution.split('x')[1]
            let edl = buildEdl(data, width, height)
            console.log('saving form', e, edl, data, data.carname)
            
            
            auth('/render', {
              method: 'post',
              params: {
                project: data.project,
                width: width,
                height: height
              },
              body: {edl: edl, duration: data.duration}
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

function buildEdl(data, width, height) {
  data.project = 'Magnussens'
  let start = data.duration == 15 ? 8 : 17.2
  let duration = data.duration == 15 ? 5 : 7
  if (data.project == 'RSG') {
    start -= 2.7
    duration += 3.5
  }
  return [
    {
      type: 'video',
      name: data.project == 'Magnussens' ? 'https://storage.googleapis.com/tower-bucket/alfred/car/Magnussens%20(check%20out%20offer).mp4' : 'https://storage.googleapis.com/tower-bucket/alfred/car/315048_MUL_MY21_MRE_RSG_LVStory_Downtown_Non-New_ENG_17-10-03_ProdAssetDlrNFA_SSSH2955000H.mp4',
      duration: data.duration,
      start: 0,
      inpoint: data.project == 'Magnussens' ? 0 : 7
    },
    data.project == 'Magnussens' ? {
      type: 'template',
      name: 'makeColor',
      duration: duration,
      start: start,
      data: {
        color: [255,255,255],
        opacity: 1,
      }
    } : null,
    {
      type: 'template',
      name: 'textBox',
      duration: duration,
      start: start,
      data: {
        text: data.carname,
        color: '#EB0A1E',
        textsize: [Math.floor(.9*width), Math.floor(.3*height)],
        font: 'Toyota-Type-Bold',
        fontsize: Math.pow(width*height, .5)/15,
        position: ['center', Math.floor(.1*height)],
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
        textsize: [Math.floor(.9*width), Math.floor(.5*height)],
        font: 'Toyota-Type',
        fontsize: Math.pow(width*height, .5)/30,
        opacity: 1,
        position: 'center',
        align: data.offeralign == 'left' ? 'west' : data.offeralign,
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
        method: 'caption',
        textsize: [Math.floor(.9*width), Math.floor(.35*height)],
        font: 'Toyota-Type-Book',
        fontsize: Math.pow(width*height, .5)/60,
        position: ['center', 'bottom'],
        align: 'west',
        opacity: 1,
      }
    },
    data.project == 'Magnussens' ? {
      type: 'image',
      name: 'https://storage.googleapis.com/tower-bucket/alfred/car/magnussens-screengrab%20logo-fixed-with-toyota.png',
      position: ['center', 'top'],
      resize: Math.pow(width*height, .5)/3600,
      start: start,
      duration: duration,
    } : null,
  ].filter(Boolean)
}