import m from 'mithril'
import { User } from './User'
import { auth } from './Login'
import { success, error, message, prompt } from 'alertifyjs'
import { downloadFile } from './Tools'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
import './styles/renders.scss'
import './styles/tables.scss'

var Stream = require('mithril/stream')

function tsToDate(ts) {
  let date = new Date(
    ts.substr(0, 4),
    ts.substr(4, 2) - 1,
    ts.substr(6, 2),
    ts.substr(9, 2),
    ts.substr(11, 2),
    ts.substr(13, 2)
  )
  return date
}

function timeDelta(date) {
  let now = new Date()
  let delta = (now - date) / 1000
  let days = Math.floor(delta / 3600 / 24)
  let hours = Math.floor(delta / 3600)
  let minutes = String(Math.floor((delta % 3600) / 60)).padStart(2, '0')
  let seconds = String(Math.floor(delta % 60)).padStart(2, '0')
  return days ? days + 'd' : hours + ':' + minutes + ':' + seconds
}

function shortTime(date) {
  let now = new Date()
  let delta = (now - date) / 1000
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
      return link
        ? m('.bar', {}, [
            m(
              'textarea',
              {
                id: vnode.attrs.id,
              },
              link
            ),
            m(
              'i.material-icons',
              {
                onclick: e => {
                  // console.log('copied ', e)
                  success('copied link to clipboard!', 3)
                  let txt = document.getElementById(vnode.attrs.id)
                  txt.select()
                  document.execCommand('copy')
                },
              },
              'content_copy'
            ),
          ])
        : m(
            '.tools',
            m(
              'i.material-icons',
              {
                onclick: e => {
                  // console.log('getting render link', vnode.children)
                  auth('/render/' + vnode.attrs.id, {}).then(res => {
                    link = res
                  })
                },
              },
              'link'
            )
          )
    },
  }
}
export function RenderPreview() {
  return {
    view: vnode => {
      return m('video', {
        width: '100%',
        'object-fit': 'contain',
        src: vnode.attrs.src,
        controls: true,
        autoplay: true,
        volume: 0.2,
      })
    },
  }
}

export function Renders() {
  var preview = Stream(null)
  var renders = []

  function getRenders() {
    auth('/render').then(e => {
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
        m('h1', 'Renders'),
        m('.renderVideo', [
          m(RenderPreview, {
            src: preview(),
          }),
        ]),
        m('.flexwrap', {}, [
          m(
            'table.rendTableHead',
            m('th', 'Project'),
            m('th', 'Description'),
            m('th', 'Duration'),
            m('th', 'Resolution'),
            m('th', 'Quality'),
            m('th', 'Start Time'),
            m('th', 'Progress'),
            m('th', 'Preview'),
            m('th', 'Link'),
            m('th', 'Issue'),
            m('th', 'Delete')
          ),
          m('table.rendTable', {}, [
            renders.map(r => {
              return m('tr', {}, [
                m('td', {}, r['project']),
                m('td', {}, r['description']),
                m('td', {}, r['duration']),
                m('td', {}, `${r['width']}x${r['height']}`),
                m('td', {}, r['quality']),
                m('td.tooltip', {}, [
                  shortTime(dateFromObjectId(r['_id'])),
                  m(
                    '.tooltiptext',
                    {},
                    dateFromObjectId(r['_id']).toLocaleString()
                  ),
                ]),
                m('td', {}, [
                  m('progress', {
                    max: 100,
                    value: `${Number(r['progress']).toFixed(2)}`,
                  }),
                  m('p', `${Number(r['progress']).toFixed(2)}%`),
                ]),
                m(
                  'td',
                  r['progress'] >= 100
                    ? m(
                        '.tools',
                        m(
                          'i.material-icons',
                          {
                            onclick: e => {
                              auth('/render/' + r['_id']).then(res => {
                                // console.log('got signed link', res)
                                preview(res)
                              })
                            },
                          },
                          'missed_video_call'
                        )
                      )
                    : ''
                ),
                m(
                  'td',
                  r['progress'] >= 100 ? m(RenderLink, { id: r['_id'] }) : ''
                ),
                m(
                  'td',
                  {},
                  m(
                    '.tools',
                    {},
                    m(
                      'i.material-icons',
                      {
                        onclick: e => {
                          prompt(
                            'Report issue',
                            'Please provide a detailed description of the issue',
                            "There's a problem with...",
                            (evt, issue) => {
                              console.log('reporting issue', evt, issue)
                              auth(`/render/${r['_id']}/report`, {
                                method: 'post',
                                body: issue,
                              }).then(
                                win => {
                                  success(
                                    "issue submitted! We'll check it out as soon as we can!"
                                  )
                                },
                                lose => {
                                  console.log('error reporting issue', lose)
                                  error('Oops... something went wrong. Sorry!')
                                }
                              )
                            },
                            evt => {
                              console.log('cancelled issue')
                            }
                          )
                        },
                      },
                      'report_problem'
                    )
                  )
                ),
                m(
                  'td',
                  m(
                    '.tools',
                    m(
                      'i.material-icons',
                      {
                        onclick: e => {
                          auth(`/render/${r['_id']}`, {
                            method: 'delete',
                          })
                            .then(
                              res => {
                                console.log('deleted', r['filename'])
                                message(`${r['filename']} removed`, 4)
                                getRenders()
                              },
                              err => {
                                console.log('error deleting', err)
                                if (err.status_code == 406) {
                                  error('did not find that entry', 4)
                                } else {
                                  error('error removing from db', 4)
                                }
                              }
                            )
                            .catch()
                        },
                      },
                      'delete'
                    )
                  )
                ),
              ])
            }),
          ]),
        ]),
      ]
    },
  }
}
