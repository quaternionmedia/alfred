import m from 'mithril'
import { record } from 'rrweb'
import '../node_modules/rrweb-player/dist/style.css'
import rrwebPlayer from 'rrweb-player'
import { state } from './Globals'
import { Menu, Link} from './Menu'

let recorder = null
let replayer = null

export function Record() {
  return {
    oncreate: vnode => {

    },
    view: vnode => {
      return [
        m('.bar', {}, [
          m(Menu),
          recorder ? m('input', {
            type: 'submit',
            value: 'stop',
            onclick: e => {
              console.log('stopping recorder')
              recorder()
              recorder = null
            }
          }) :
          m('input', {
            type: 'submit',
            value: 'record',
            onclick: e => {
              console.log(e)
              e.preventDefault()
              recorder = record({
                emit(event) {
                  console.log('event', event)
                  state.events.push(event)
                }
              })

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
