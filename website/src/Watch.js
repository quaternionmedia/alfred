import m from 'mithril'
import '../node_modules/rrweb/dist/rrweb.min.css'
import { Menu } from './Menu'
import { Replayer } from 'rrweb'

let replayer = null
let ws = null

export function Watch() {
  let sessions = []
  return {
    oninit: vnode => {
      m.request('/sessions').then(res => {
        sessions = res
      })
    },
    oncreate: vnode => {
      replayer = new Replayer([], {
        root: document.getElementById('replay'),
        liveMode: true,
      })
      replayer.startLive()
      // replayer = new rrwebPlayer({
      //   target: document.getElementById('replay'),
      //   data: {
      //     autoPlay: false,
      //     showController: true,
      //     events: [],
      //   }})}
    },
    view: vnode => {
      return [
        m(Menu),
        sessions.map(s => {
          return m('', {
            onclick: e => {


            }
          }, s)
        }),
        m('input', {
          type: 'submit',
          value: 'play',
          onclick: e => {
            if (!ws) {
              ws = new WebSocket(`ws://${location.host}/watch`)
              ws.onopen = () => {
                console.log('opened ws connection')
              }
              ws.onmessage = (m) => {
                console.log('got event ', m)
                  replayer.addEvent(JSON.parse(m.data))
              }
            }
          }
        }),
        m('#replay'),
      ]
    }
  }
}
