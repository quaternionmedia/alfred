import m from 'mithril'
import { Menu, Link} from './Menu'
import { User } from './User'
import { auth } from './Login'
import { success, error, message } from 'alertifyjs'
import { downloadFile } from './Tools'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
var Stream = require("mithril/stream")

export function RenderLink() {
  var link = null
  return {
    view: vnode => {
      return link ? m('.bar', {}, [
        m('textarea', {
          id: vnode.children[0]
        }, link),
        m('i.material-icons', {
          onclick: e => {
            // console.log('copied ', e)
            success('copied link to clipboard!', 3)
            let txt = document.getElementById(vnode.children[0])
            txt.select()
            document.execCommand('copy')
          }
        }, 'content_copy')
      ]) : m('.tools',
          m('i.material-icons', {
            onclick: e => {
              // console.log('getting render link', vnode.children)
              auth('/render', {
                params: { name: vnode.children[0] }
              }).then(res => {
                link = res
              })
            }}, 'link'))
    }
  }
}
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
    auth('/renders').then(e => {
      console.log('renders init')
      renders = JSON.parse(e)
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
            m('th', 'link'),
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
                    onclick: e => {
                      auth('/render', {
                        params: { name: r['filename'] }
                      }).then(res => {
                        // console.log('got signed link', res)
                        preview(res)
                      })
                    }}, 'missed_video_call')) : ''),
              m('td', r['progress'] >= 100 ?
                m(RenderLink, {}, r['filename']) : ''),
                m('td',
                  m('.tools',
                    m('i.material-icons', {
                      onclick: e => {
                        auth(`/renders/${r['filename']}/cancel`, {
                          method: 'put',
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
