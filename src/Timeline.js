import m from 'mithril'
import Sortable from 'sortablejs'
// var Clip = require('./Clip').Clip
import Clip from './Clip'
var state = require("./Globals").state

// import csvStringToArray from "./parseCsv"
const csvStringToArray = require('./parseCsv').csvStringToArray

var Timeline = {
  // edl: [],
  oninit: (vnode) => {
    m.request('/edl.csv', {extract: (xhr) => {return {status: xhr.status, body: xhr.responseText}}}).then((e) => {
      // console.log(e)
    state.edl(csvStringToArray(e.body))
    // console.log(Timeline.edl)
    })

  },
  oncreate: (vnode) => {
    new Sortable(vnode.dom, {
      swapThreshold: 0.50,
      animation: 150,
      // ghostClass: 'blue-background-class',
      ghostClass: 'ghost',
      forceFallback: true,
      // delay: 100,
      filter: (e) => {
        var cursor = e.target.style.cursor;
        // console.log('filter: ', e, cursor)
        return cursor == 'ew-resize'
      }

    })
    
  },
  view: (vnode) => {
    return m('#timeline.timeline', [
      // m(Clip)
      state.edl().map((c) => {
        return m(Clip, {name: c[0], inpoint: c[1], outpoint: c[2], duration: c[3], description: c[4]})

      })
    ])
  },
}

module.exports = {
  view: (vnode) => {
    return m(Timeline)
  }
}
