import m from 'mithril'
import JsonViewer from 'mithril-json-viewer'
import './json.css'
import { auth } from './Login'

export const TemplateEditor = () => {
  let projectName
  let logic
  let fields
  return {
    oninit: vnode => {
      projectName = m.route.param('project')
      // Same guard as OttoTimeline: without a ?project= parameter this asked
      // for /project/undefined, which is not a request worth making.
      if (!projectName) {
        return
      }
      auth('/project/' + projectName)
        .then(res => {
          logic = res.logic
          fields = res.fields
        })
        .catch(err => {
          console.error('could not load the project template', err)
        })
    },
    view: vnode => {
      // Reached with no ?project=, this rendered the headings over two empty
      // viewers -- "logic undefined fields undefined" -- which reads as a
      // broken page rather than one waiting for a choice. The menu links here
      // without a project, so it is the normal way in, not an edge case.
      if (!projectName) {
        return m('.json-tree', {}, [
          m('h2', {}, 'Template editor'),
          m('p.empty', {}, [
            'Choose a project to edit its template. ',
            m('a', { href: '#!/projects' }, 'Projects'),
          ]),
        ])
      }
      return m('.json-tree', {}, [
        m('h2', {}, projectName),
        m('h3', {}, 'logic'),
        m(JsonViewer, {tree: logic}),
        m('h3', {}, 'fields'),
        m(JsonViewer, {tree: fields}),
      ])
    }
  }
}