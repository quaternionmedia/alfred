import m from 'mithril'
import { Edl } from './Video'
import { User } from './User'
import { error } from 'alertifyjs'
import { auth } from './Login'
import './styles/projects.scss'
import './styles/tables.scss'

export function Projects() {
  var projects = []
  return {
    oninit: vnode => {
      auth('/project').then(
        e => {
          console.log('got projects', e)
          projects = e
        },
        err => {
          console.log('error loading projects from server', err)
        }
      )
    },
    view: vnode => {
      return [
        m('h1', 'Projects'),
        m('.projects', [
          m('table.projTableHead', [
            m('th', 'Name'),
            m('th', 'Edit Template'),
            m('th', 'Create New Video'),
          ]),
          m(
            '.projTableContainer',
            m('table.projTable', {}, [
              projects.map(p => {
                return m('tr', [
                  m('td', p['name']),
                  m(
                    'td',
                    m(
                      'i.material-icons',
                      {
                        onclick: e => {
                          m.route.set('/editor?project=' + p['_id'])
                        },
                      },
                      'edit'
                    )
                  ),
                  m(
                    'td',
                    m(
                      'i.material-icons',
                      {
                        onclick: e => {
                          m.route.set('/form?project=' + p['_id'])
                        },
                      },
                      'video_call'
                    )
                  ),
                ])
              }),
            ])
          ),
        ]),
      ]
    },
  }
}
