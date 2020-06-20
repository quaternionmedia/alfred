import m from 'mithril'
import { Menu, Link} from './Menu'
import { User } from './User'
import { error } from 'alertifyjs'
import { downloadFile } from './Tools'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
var Stream = require("mithril/stream")

export function RenderPreview() {
  return {
    view: (vnode) => {
      return m('video', {
        width: '100%',
        'object-fit': 'contain',
        src: vnode.attrs.src,
        controls: true,
      })
    }
  }
}

export function Renders() {
  var preview = Stream(null)
  var renders = []
  function getRenders() {
    m.request('/renders', {
      headers: {
        Authorization: User.token
      }
    }).then( e => {
      console.log('render list:', e)
      renders = JSON.parse(e)
    }, (err) => {
      error('Not authorized!', 3)
      console.log('error loading renders from server', err)
      m.route.set('/login?redirect=/renders')
    })
  }
  return {
    oninit: vnode => {
      getRenders()
    },
    view: vnode => {
      return [
        m(Menu),
        m('h3', 'Renders'),
        m('.tools', [
          m('i.material-icons', {
            onclick: vnode => { getRenders() }
          }, 'refresh'),
        ]),
        m('table#renders.bin.project', {}, [
          m('tr', [
            m('th', 'edl'),
            m('th', 'progress'),
            m('th', 'link'),
          ],),
          renders.map(r => {
            return m('tr', {}, [
              m('td', {}, r['filename']),
              m('td', {}, r['progress']),
              m('td', {
              }, m('p', {
                onclick: (vnode) => {
                  preview(r['link'])
                }
              }, r['link'])),
            ])
          })
        ]),
        m(RenderPreview, {
          src: preview()
        })
      ]
    }
  }
}
