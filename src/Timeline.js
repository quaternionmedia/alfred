import m from 'mithril'
import interact from 'interactjs'
// import dragula from 'dragula'
import Sortable from 'sortablejs'
var state = require("./Globals").state
function seconds(t) {
  t = t.split(":")
  console.log('splitting', t)
  var v = 3600*parseInt(t[0]) + 60*parseInt(t[1]) + parseInt(t[2])
  console.log('v', v)
  return v
}
// import csvStringToArray from "./parseCsv"
const csvStringToArray = strData =>
{
    const objPattern = new RegExp(("(\\,|\\r?\\n|\\r|^)(?:\"([^\"]*(?:\"\"[^\"]*)*)\"|([^\\,\\r\\n]*))"),"gi");
    let arrMatches = null, arrData = [[]];
    while (arrMatches = objPattern.exec(strData)){
        if (arrMatches[1].length && arrMatches[1] !== ",")arrData.push([]);
        arrData[arrData.length - 1].push(arrMatches[2] ?
            arrMatches[2].replace(new RegExp( "\"\"", "g" ), "\"") :
            arrMatches[3]);
    }
    arrData = arrData.slice(1)

    for (var i = 0; i < arrData.length; i++) {
      arrData[i] = arrData[i].map(col => col.includes(":") && !col.includes("M") ? seconds(col) : col
      )
    }
    console.log(arrData)
  // )
    // return arrData.includes(":") ? seconds(arrData) : arrData;
    return arrData
}

class Clip {
  constructor(vnode) {
    this.inpoint = vnode.attrs.inpoint
    this.outpoint = vnode.attrs.outpoint
    this.description = vnode.attrs.description
    console.log('clip init', vnode, this.inpoint, this.outpoint)
    }

  oninit(vnode) {
  }
  oncreate(vnode) {
    const clip = interact(vnode.dom)
    clip.on('resizemove', (event) => {
      let target = event.target
    // console.log('event: ', event) //event.delta.x, )
    var w = parseInt(target.style.width)
    // console.log( w - (vnode.state.outpoint - vnode.state.inpoint), event.rect.width, vnode.state.outpoint, vnode.state.inpoint, w)
    if (event.edges.left && ( vnode.state.outpoint > vnode.state.inpoint + event.dx)) {
      // target.style.width  = event.rect.width + 'px';
      target.style.width = w - event.dx + 'px'
      vnode.state.inpoint += event.dx
      target.setAttribute('inpoint', vnode.state.inpoint)
      // console.log('changing inpoint', vnode, event)
    } else if (event.edges.right && (vnode.state.outpoint + event.dx > vnode.state.inpoint)) {
      target.style.width  = w + event.dx + 'px';
      vnode.state.outpoint += event.dx
      target.setAttribute('outpoint', vnode.state.outpoint)
      // console.log('changing outpoint', event.deltaRect, event)
    }
    target.innerHTML= `${vnode.state.description} - [${vnode.state.inpoint}, ${vnode.state.outpoint}]`
    // m.redraw()
    })
    clip.resizable({
      edges: {
        left: true,
        right: true,
      }
    })
    clip.on('resizestart', (event) => {
      state.resizing(true)
      console.log('resize start', state.resizing())
    })
    clip.on('resizeend', (event) => {
      state.resizing(false)
      console.log('resize stop', state.resizing())
    })
  }
  view(vnode) {
    return m(`.clip#${vnode.attrs.name}`, {
      'data-x': vnode.state.inpoint, // /state.scale(),
      // 'data-duration': vnode.attrs.duration/scale,
      innerHTML: `${vnode.state.description} - [${vnode.state.inpoint}, ${vnode.state.outpoint}]`,
      inpoint: vnode.state.inpoint,
      outpoint: vnode.state.outpoint,
      style: {
        width: vnode.state.outpoint - vnode.state.inpoint,
      },
      }, [
      ])
      // {data-x: vnode.attrs.inpoint/scale, data-y: vnode.attrs.outpoint/scale})
  }
}

var Timeline = {
  edl: [],
  oninit: (vnode) => {

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
        console.log('filter: ', e, cursor)
        return cursor == 'ew-resize'
      }

    })
      m.request('/edl.csv', {extract: (xhr) => {return {status: xhr.status, body: xhr.responseText}}}).then((e) => {
        // console.log(e)
      Timeline.edl = csvStringToArray(e.body)
      // console.log(Timeline.edl)
    })

  },
  view: (vnode) => {
    return m('#timeline.timeline', [
      // m(Clip)
      Timeline.edl.map((c) => {
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
