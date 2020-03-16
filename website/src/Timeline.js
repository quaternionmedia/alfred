import m from 'mithril'
import { Sortable, MultiDrag } from 'sortablejs'
Sortable.mount(new MultiDrag());
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
    var edl = []
    let clips = Timeline.v.dom.children
    // let clips = document.getElementById('timeline').children
    // console.log('updating edl', clips)
    for (var i = 0; i < clips.length; i++) {
      // console.log(i, clips[i])
      edl.push([
        clips[i].attributes.filename.value,
        Number(clips[i].attributes.inpoint.value),
        Number(clips[i].attributes.outpoint.value),
        Number(clips[i].attributes.outpoint.value - clips[i].attributes.inpoint.value),
        clips[i].attributes.description.value
      ])
      clips[i].attributes.pos.value = i
    }
    Edl.edl = edl
    m.redraw()
  },
  loadEdl: (edl) => {
    Edl.edl = []
    m.redraw.sync()
    Edl.edl = edl
    m.redraw()
  },
  oninit: (vnode) => {
    Timeline.v = vnode
    // m.request(m.route.param('edl') || 'test.csv', {extract: (xhr) => {return {status: xhr.status, body: xhr.responseText}}}).then((e) => {
    //   console.log('got edl!', e)
    // // Edl.edl = csvStringToArray(e.body)
    // Edl.edl = edlToSeconds(CSVToArray(e.body))
    m.request({
      url: '/edl',
      params: {
        filename: m.route.param('edl')
      }
    }).then(e => {
      let edl
      if (e.length) {
        edl = e
      } else {
        edl = edlToSeconds(CSVToArray(e))
      }
      console.log('got edl!', e, edl)
      Edl.edl = edl
      Video.filename = Edl.edl[0][0]
      Video.time = Edl.edl[0][1]
      Monitor.load(Video.filename)
    })
    // m.redraw()
    // Monitor.play()
    // })

  },
  oncreate: (vnode) => {
    new Sortable(vnode.dom, {
      multiDrag: true,
      group: 'media',
      selectedClass: "selected",
      swapThreshold: 0.50,
      animation: 150,
      ghostClass: 'ghost',
      forceFallback: true,
      // delay: 100,
      invertSwap: true,
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
      },
      removeOnSpill: true,
      onSpill: e => {
        console.log('spilling', e)
        Edl.edl.splice(e.oldIndex, 1)
        Timeline.loadEdl(Edl.edl)
        // console.log('new edl:', Edl.edl)
      }
    })
  },
  view: (vnode) => {
    return m('#timeline.timeline', [
      Edl.edl.map((c, i) => {
        return m(Clip, {filename: c[0], inpoint: c[1], outpoint: c[2], duration: c[3], description: c[4], pos: i})

      })
    ])
  },
}
