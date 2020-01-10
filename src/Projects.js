import m from 'mithril'
import { Menu } from './Menu'

const Projects = () => {
  var projects = []
  return {
    oninit: (vnode) => {
      m.request('/projects').then(e => {
        console.log('got projects', e)
        projects = e
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
                  m.route.set('/timeline?edl=' + p)
                  }}, p),
              ])
            })
          ])
      ])]
    }
  }
}

export default Projects
