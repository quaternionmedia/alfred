import m from 'mithril'
import { record } from 'rrweb'
import '../node_modules/rrweb-player/dist/style.css'
import rrwebPlayer from 'rrweb-player'
import { state } from './Globals'
import { Menu, Link} from './Menu'
var Stream = require("mithril/stream")

let recording = Stream(false)
let recorder = null
let replayer = null

let ws = null

export function Record() {
  return {
    oninit: vnode => {

    },
    view: vnode => {
      return [
        m('.bar', {}, [
          m(Menu),
          recording() ? m('input', {
            type: 'submit',
            value: 'stop',
            onclick: e => {
              console.log('stopping recorder')
              recorder()
              ws.close()
              ws = null
              recording(false)
              // m.redraw.sync()
            }
          }) :
          m('input', {
            type: 'submit',
            value: 'record',
            onclick: e => {
              // e.preventDefault()
              if (!ws) {
                ws = new WebSocket(`ws${ location.protocol !== 'https:' ? '' : 's' }://${location.host}/record`)
                ws.onopen = () => {
                  recording(true)
                  m.redraw.sync()
                  console.log('opened ws connection')
                  recorder = record({
                    emit(event) {
                      console.log('event', event)
                      if (ws) {
                        ws.send(JSON.stringify(event))
                      }
                    }
                  })
                }
              }

            }
          }),
          m('input', {
            type: 'submit',
            value: 'play',
            onclick: e => {
              if (!replayer) {
                replayer = new rrwebPlayer({
                  target: document.getElementById('replay'),
                  data: {
                    autoPlay: true,
                    showController: true,
                    events: state.events,
                  }})}
            }
          }),
        ]),
        m('#replay'),
      ]
    }
  }
}
