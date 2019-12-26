import m from 'mithril'
import Sortable from 'sortablejs'
// var Clip = require('./Clip').Clip
import Clip from './Clip'
var state = require("./Globals").state
function seconds(t) {
  t = t.split(":")
  // console.log('splitting', t)
  var v = 3600*parseInt(t[0]) + 60*parseInt(t[1]) + parseInt(t[2])
  // console.log('v', v)
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
