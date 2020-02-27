import m from 'mithril'
import Sortable from 'sortablejs'
// var Clip = require('./Clip').Clip
import Clip from './Clip'
var state = require("./Globals").state
import { Video, Edl } from './Video'
import Monitor from './Monitor'

// const csvStringToArray = require('./parseCsv').csvStringToArray
const CSVToArray = require('./CSVToArray').CSVToArray
const edlToSeconds = require('./CSVToArray').edlToSeconds

export var Timeline = {
  // constructor() {
    // edl: [],
    // duration: 0,
  // }
  v: null,
  updateEdl: () => {
    // console.log('updating edl')
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
    Edl.edl = edl
    // Timeline.duration =
    m.redraw()
    // state.edl(this.edl)
  },
  oninit: (vnode) => {
    Timeline.v = vnode
    m.request(m.route.param('edl') || 'test.csv', {extract: (xhr) => {return {status: xhr.status, body: xhr.responseText}}}).then((e) => {
      console.log('got edl!', e)
    // Edl.edl = csvStringToArray(e.body)
    Edl.edl = edlToSeconds(CSVToArray(e.body))
    Video.filename = Edl.edl[0][0]
    Video.time = Edl.edl[0][1]
    Monitor.load(Video.filename)
    // m.redraw()
    // Monitor.play()
    })

  },
  oncreate: (vnode) => {
    new Sortable(vnode.dom, {
      swapThreshold: 0.50,
      animation: 150,
      ghostClass: 'ghost',
      forceFallback: true,
      // delay: 100,
      preventOnFilter: false,
      filter: (e) => {
         if (state.tool() != 'move') {
           return true
         }
         else {
           return false
         }

      },
      onUpdate: (e) => {
        Edl.current = e.newIndex
        console.log('sorting update', e, Edl)
        Timeline.updateEdl()
        m.redraw()
      },
    })
  },
  view: (vnode) => {
    return m('#timeline.timeline', [
      // m(Clip)
      Edl.edl.map((c, i) => {
        return m(Clip, {filename: c[0], inpoint: c[1], outpoint: c[2], duration: c[3], description: c[4], pos: i})

      })
    ])
  },
}
