import m from 'mithril'
import { Menu } from './Menu'
import { Edl } from './Video'
import { User } from './User'
import { error } from 'alertifyjs'
import { auth } from './Login'

function Projects() {
  var projects = []
  return {
    oninit: (vnode) => {
      auth('/projects')
      .then(e => {
        console.log('got projects', e)
        projects = e
      }, (err) => {
        console.log('error loading projects from server', err)
      })
    },
    view: (vnode) => {
      return [
        m(Menu),
        m('.projects', [
          m('h3', 'projects:'),
          m('table.project.projects', {}, [
            m('tr', [
              m('th', 'name'),
            ]),
            projects.map(p => {
              return m('tr', [
                m('td', {onclick: (e) => {
                  Edl.edl = []
                  m.route.set('/form?project=' + p)
                  }}, p),
              ])
            })
          ])
      ])]
    }
  }
}

export default Projects
