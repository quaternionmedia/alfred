import m from 'mithril'
import Sortable from 'sortablejs'
// var Clip = require('./Clip').Clip
import Clip from './Clip'
var state = require("./Globals").state

// import csvStringToArray from "./parseCsv"
const csvStringToArray = require('./parseCsv').csvStringToArray

export var Timeline = {
  // constructor() {
    edl: [],
    duration: 0,
    v: null,
  // }
  updateEdl: () => {
    var edl = []
    let clips = Timeline.v.dom.children
    for (var i = 0; i < clips.length; i++) {
      // console.log(clips[i])
      edl.push([
        clips[i].attributes.filename.value,
        clips[i].attributes.inpoint.value,
        clips[i].attributes.outpoint.value,
        clips[i].attributes.outpoint.value - clips[i].attributes.inpoint.value,
        clips[i].attributes.description.value
      ])
    }
    Timeline.edl = edl
    Timeline.duration =
    m.redraw()
    // state.edl(this.edl)
  },
  updateDuration: () => {
    Timeline.duration = Timeline.edl.reduce((a, b) => a + b[3], 0)
  },
  oninit: (vnode) => {
    Timeline.v = vnode
    m.request('/edl.csv', {extract: (xhr) => {return {status: xhr.status, body: xhr.responseText}}}).then((e) => {
      // console.log(e)
    Timeline.edl = csvStringToArray(e.body)
    Timeline.updateDuration()
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
        var left = Math.abs(e.target.offsetLeft - e.clientX) <= 25
        var right = Math.abs(e.target.offsetLeft + e.target.offsetWidth - e.clientX) <= 25
        console.log('right', right, e)
        // console.log('filter: ', e, cursor)
         if (cursor == 'ew-resize' || left || right) {
           return true
         } else {
           // e.preventDefault()
           e.stopPropagation()
           return false
         }
        // return cursor == 'ew-resize' || left || right
      },
      onUpdate: (e) => {
        console.log(e)
        Timeline.updateEdl()
      },
    })
  },
  view: (vnode) => {
    return m('#timeline.timeline', [
      // m(Clip)
      Timeline.edl.map((c) => {
        return m(Clip, {filename: c[0], inpoint: c[1], outpoint: c[2], duration: c[3], description: c[4]})

      })
    ])
  },
}
