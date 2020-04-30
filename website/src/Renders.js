import m from 'mithril'
import { Menu } from './Menu'
import { downloadFile } from './Tools'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'


export const Renders = () => {
  var renders = []
  function getRenders() {
    m.request('/renders').then( e => {
      console.log('render list:', e)
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
        m('h3', 'Renders'),
        m('.tools', [
          m('i.material-icons', {
            onclick: vnode => { getRenders() }
          }, 'refresh'),
        ]),
        m('table#renders.bin.project', {}, [
          m('tr', [
            m('th', 'edl'),
            m('th', 'progress'),
            m('th', 'link'),
          ],),
          renders.map(r => {
            return m('tr', {}, [
              m('td', {}, r['filename']),
              m('td', {}, r['progress']),
              m('td', {
                onclick: vnode => {
                  downloadFile(`download?filename=${r['filename']}`)
                }
              }, r['link']),
            ])
          })
        ])
      ]
    }
  }
}
