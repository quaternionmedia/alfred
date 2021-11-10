import m from 'mithril'
import { User } from './User'
import { auth } from './Login'
import { success, error, message, prompt } from 'alertifyjs'
import { downloadFile } from './Tools'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
var Stream = require("mithril/stream")

function tsToDate(ts) {
  let date = new Date(ts.substr(0,4), ts.substr(4,2) - 1, ts.substr(6, 2), ts.substr(9, 2), ts.substr(11, 2) , ts.substr(13, 2))
  return date
}

function timeDelta(date) {
  let now = new Date()
  let delta = (now - date)/1000
  let days = Math.floor(delta / 3600 / 24)
  let hours = Math.floor(delta / 3600)
  let minutes = String(Math.floor((delta  % 3600) / 60)).padStart(2, '0')
  let seconds = String(Math.floor(delta % 60)).padStart(2, '0')
  return days ? days + 'd' : hours + ':' + minutes + ':' + seconds
}

function shortTime(date) {
  let now = new Date()
  let delta = (now - date)/1000
  let days = Math.floor(delta / 3600 / 24)
  return days ? days + 'd' : date.toLocaleTimeString()
}

export const dateFromObjectId = function (objectId) {
	return new Date(parseInt(objectId.substring(0, 8), 16) * 1000)
}

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
        autoplay: true,
        volume: .2,
      })
    }
  }
}

export function Renders() {
  var preview = Stream(null)
  var renders = []
  
  function getRenders() {
    auth('/renders').then(e => {
      // console.log('renders init')
      renders = e
    })
  }
  
  return {
    oncreate: vnode => {
      function checkRenders() {
        if (m.route.get() == '/renders') {
          getRenders()
          setTimeout(() => {
            checkRenders()
          }, 1000)
        }
      }
      checkRenders()
    },
    view: vnode => {
      let now = new Date()
      return [
        m('.head', [
          m(RenderPreview, {
            src: preview()
          })
        ]),
        m('.flexwrap', {}, [
          m('h3', 'Renders'),
          m('.tools', [
            m('i.material-icons', {
              style: { 'margin-left': '2vw', },
              onclick: vnode => { getRenders() }
            }, 'refresh'),
          ]),
          m('.break'),
          m('table#renders.renders.project', {}, [
            m('tr', [
              m('th', 'project'),
              m('th', 'description'),
              m('th', 'duration'),
              m('th', 'resolution'),
              m('th', 'quality'),
              m('th', 'start time'),
              m('th', 'progress'),
              m('th', 'preview'),
              m('th', 'link'),
              m('th', 'issue'),
              m('th', 'delete'),
            ],),
            renders.map(r => {
              return m('tr', {}, [
                m('td', {}, r['project']),
                m('td', {}, r['description']),
                m('td', {}, r['duration']),
                m('td', {}, r['resolution'] ? `${r['resolution'][0]}x${r['resolution'][1]}` : ''),
                m('td', {}, r['quality']),
                m('td.tooltip', {}, [
                  shortTime(dateFromObjectId(r['_id'])),
                  m('.tooltiptext', {}, dateFromObjectId(r['_id']).toLocaleString())
                ]),
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
                  m('td', {}, m('.tools', {}, m('i.material-icons', {
                    onclick: e => {
                      prompt('Report issue', "Please provide a detailed description of the issue", "There's a problem with...", (evt, issue) => {
                        console.log('reporting issue', evt, issue)
                        auth('/report', {
                          method: 'post',
                          params: { name: r['filename'] },
                          body: issue
                        }).then(win => {
                          success("issue submitted! We'll check it out as soon as we can!")
                        }, lose => {
                          console.log('error reporting issue', lose)
                          error('Oops... something went wrong. Sorry!')
                        })
                      }, evt => {
                        console.log('cancelled issue')
                      })
                    }
                  }, 'report_problem'))),
                  m('td',
                  m('.tools',
                  m('i.material-icons', {
                    onclick: e => {
                      auth(`/renders/${r['filename']}/cancel`, {
                        method: 'put',
                      }).then(res => {
                        console.log('deleted', r['filename'])
                        message(`${r['filename']} removed`, 4)
                        getRenders()
                      }, err => {
                        console.log('error deleting', err)
                        if (err.status_code == 406) {
                          error('did not find that entry', 4)
                        } else {
                          error('error removing from db', 4)
                        }
                      }).catch()
                    },
                  }, 'delete'))),
                ])
              }),
            ]),
        ]),
        ]
      }
    }
  }
