import m from 'mithril'
import { Menu } from './Menu'
import { downloadFile } from './Tools'

export const Renders = () => {
  var renders = []
  return {
    oninit: vnode => {
      m.request('/renders').then( e => {
        console.log('render list:', e)
        renders = JSON.parse(e)
      })
    },
    view: vnode => {
      return [
        m(Menu),
        m('h3', 'Renders'),
        m('table#renders.bin.project', {}, [
          m('tr', [
            m('th', 'edl'),
            m('th', 'progress'),
            m('th', 'link'),
          ],),
          renders.map(r => {
            return m('tr', {}, [
              m('td', {}, r['edl']),
              m('td', {}, r['progress']),
              m('td', {
                onclick: vnode => {
                  downloadFile(`download?filename=${r['edl']+'.mp4'}`)
                }
              }, r['link']),
            ])
          })
        ])
      ]
    }
  }
}
