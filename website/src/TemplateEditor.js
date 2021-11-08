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
      auth('/project/' + projectName).then(res => {
        console.log('got project', res)
        logic = res.logic
        fields = res.fields
      }).catch(err => {
        console.log('error getting project')
      })
    },
    view: vnode => {
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