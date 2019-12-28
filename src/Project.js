import m from 'mithril'
var state = require("./Globals").state
var Timeline = require("./Timeline").Timeline

module.exports = {
  view: (vnode) => {
    return m('table#project.project', {}, [
      m('tr', [
        m('th', 'name'),
        m('th', 'inpoint'),
        m('th', 'outpoint'),
        m('th', 'duration'),
      ]),
      Timeline.edl.map(c => {
        // console.log('project clip: ', c)
      return m('tr', [
        m('td', c[0]),
        m('td', c[1]),
        m('td', c[2]),
        m('td', c[2] - c[1]),
      ])
    })])
  }
}
