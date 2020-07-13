import m from 'mithril'
import { Menu, Link} from './Menu'
import { User } from './User'
import { error, message } from 'alertifyjs'
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
        Authorization: User.token,
        mcguffin: User.mcguffin,
      }
    }).then( e => {
      // console.log('render list:', e)
      renders = JSON.parse(e)
    }, (err) => {
      console.log('error loading renders from server', err)
      m.request('/refresh', {
          method: 'post',
      }).then(e => {
        console.log('refreshed token', e)
        User.login(e)
      }, err => {
        error('Not authorized!', 3)
        m.route.set('/login?redirect=/renders')
      })
    })
  }
  return {
    oninit: vnode => {
      getRenders()
    },
    view: vnode => {
      return [
        m(Menu),
        m('.head', [
          m(RenderPreview, {
            src: preview()
          })
        ]),
        m('', { style: { display: 'flex' }}, [
          m('h3', 'Renders'),
          m('.tools', [
            m('i.material-icons', {
              style: { 'margin-left': '2vw', },
              onclick: vnode => { getRenders() }
            }, 'refresh'),
          ]),
        ]),
        m('table#renders.renders.bin.project', {}, [
          m('tr', [
            m('th', 'project'),
            m('th', 'duration'),
            m('th', 'resolution'),
            m('th', 'start time'),
            m('th', 'progress'),
            m('th', 'preview'),
            m('th', 'download'),
            m('th', 'delete'),
          ],),
          renders.map(r => {
            return m('tr', {}, [
              m('td', {}, r['project']),
              m('td', {}, r['duration']),
              m('td', {}, r['resolution'] ? `${r['resolution'][0]}x${r['resolution'][1]}` : ''),
              m('td', {}, r['started']),
              m('td', {}, [
                m('progress', {
                  max: 100,
                  value: `${Number(r['progress']).toFixed(2)}`,
                }, ),
                m('p', `${Number(r['progress']).toFixed(2)}%`)
              ]),
              m('td', r['progress'] >= 100 ?
                m('.tools',
                  m('i.material-icons', {
                    onclick: e => { preview(r['link']) }}, 'missed_video_call')) : ''),
              m('td', r['progress'] >= 100 ?
                m('.tools',
                  m('a[download]', {
                    href: `download?filename=${r['link']}`,
                  }, m('i.material-icons', 'file_download'))) : ''),
                m('td',
                  m('.tools',
                    m('i.material-icons', {
                      onclick: e => {
                        m.request(`/renders/${r['filename']}/cancel`, {
                          method: 'put',
                          headers: {
                            Authorization: User.token
                          }
                        }).then(res => {
                          console.log('deleted', res)
                          if (res.status_code == 406) {
                            error('did not find that entry', 4)
                          } else {
                            message(`${r['filename']} removed`, 4)
                            getRenders()
                          }
                        }, err => {
                          console.log('error deleting', err)
                          error('error removing from db', 4)
                        })
                      },
                    }, 'delete'))),
              ])
            }),
          ]),
        ]
      }
    }
  }
