import m from 'mithril'
var state = require("./Globals").state
var Timeline = require("./Timeline").Timeline
const formatTime = require('./Slider').formatTime
import { Edl } from './Video'

module.exports = {
  view: (vnode) => {
    return m('table#project.project', {}, [
      m('tr', [
        m('th', 'name'),
        m('th', 'inpoint'),
        m('th', 'outpoint'),
        m('th', 'duration'),
        m('th', 'description'),
      ]),
      Edl.edl.map(c => {
        // console.log('project clip: ', c)
      return m('tr', [
        m('td', c[0]),
        m('td', formatTime(c[1])),
        m('td', formatTime(c[2])),
        m('td', formatTime(c[3])),
        m('td', c[4]),
      ])
    })])
  }
}
