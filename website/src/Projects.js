import m from 'mithril'
import { Edl } from './Video'
import { User } from './User'
import { error } from 'alertifyjs'
import { auth } from './Login'

export function Projects() {
  let projects = []
  return {
    oninit: (vnode) => {
      auth('/project')
      .then(e => {
        console.log('got projects', e)
        projects = e
      }, (err) => {
        console.log('error loading projects from server', err)
      })
    },
    view: (vnode) => {
      return [
        m('.projects', [
          m('h3', 'projects:'),
          m('table.project.projects', {}, [
            m('tr', [
              m('th', 'name'),
              m('th', 'edit template'),
              m('th', 'create new video'),
            ]),
            projects.map(p => {
              return m('tr', [
                m('td', {onclick: e => {
                  Edl.edl = []
                  m.route.set('/form?project=' + p['_id'])
                }}, p['name']),
                m('td', {onclick: e => {
                  m.route.set('/editor?project=' + p['_id'])
                }}, m('i.material-icons', {}, 'edit')),
                m('td', {onclick: e => {
                  m.route.set('/form?project=' + p['_id'])
                }}, m('i.material-icons', {}, 'video_call')),
              ])
            })
          ])
      ])]
    }
  }
}



export function Edls() {
  var projects = []
  return {
    oninit: (vnode) => {
      auth('/edl')
      .then(e => {
        console.log('got projects', e)
        projects = e
      }, (err) => {
        console.log('error loading projects from server', err)
      })
    },
    view: (vnode) => {
      return [
        m('.projects', [
          m('h3', 'single-track projects:'),
          m('table.project.projects', {}, [
            m('tr', [
              m('th', 'name'),
              m('th', 'edit template'),
              m('th', 'create new video'),
            ]),
            projects.map(p => {
              return m('tr', [
                m('td', {onclick: e => {
                  Edl.edl = []
                  m.route.set('/otto?project=' + p['_id'])
                }}, p['name']),
                m('td', {onclick: e => {
                  m.route.set('/editor?project=' + p['_id'])
                }}, m('i.material-icons', {}, 'edit')),
                m('td', {onclick: e => {
                  m.route.set('/otto?project=' + p['_id'])
                }}, m('i.material-icons', {}, 'video_call')),
              ])
            })
          ])
      ])]
    }
  }
}
