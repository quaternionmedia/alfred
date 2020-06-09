import m from 'mithril'
import { Sortable } from 'sortablejs'
import Clip from './Clip'
import { Timeline } from './Timeline'
import { Edl } from './Video'



var Bin = {
  media: [],
  oninit: (vnode) => {
    m.request('/videos').then( e => {
      // console.log('got videos!', e)
      Bin.media = e
    })
  },
  oncreate: vnode => {
    new Sortable(vnode.dom, {
      group: {
        name: 'media',
        pull: 'clone',
        put: false,
      },
      sort: false,
      selectedClass: "selected",
      ghostClass: 'ghost',
      forceFallback: true,
      animation: 150,
      onEnd: (e) => {
        if (e.from.id == 'bin' && e.to.id == 'timeline') {
          console.log('moved media!', e)
          var clip = e.item.attributes
          e.item.attributes.pos.value = e.newIndex
          // Timeline.updateEdl()
          // Edl.edl.splice(e.newIndex, 0, [
          var edl = Edl.edl.slice(0, e.newIndex)
          edl.push( {
            filename: clip.filename.value,
            inpoint: Number(clip.inpoint.value),
            outpoint: Number(clip.outpoint.value),
            duration: Number(clip.outpoint.value - clip.inpoint.value),
            description: clip.description.value,
          })
          edl = edl.concat(Edl.edl.slice(e.newIndex))
            console.log('inserted new clip', edl)
            if (e.newIndex <= Edl.current) {
              Edl.current++
            }
          e.item.remove()
          Timeline.loadEdl(edl)
        }
      },
    })
  },
  view: (vnode) => {
    // m('#bin.project.bin', {}, [
    //   m('h3', 'bin'),
    // m('tr', [
    //   m('th', 'files'),
    // ]),

    // return m('table#bin.project.bin', {}, [
    //     media.map(f => {
    //       return m('tr', [
    //         m('td', {
    //         }, f)
    //       ])
    //     })
    //   ])

    return [
      m('table#bin.bin.project', {}, [
      Bin.media.map(f => {
      return m(Clip, {filename: f, inpoint: 0, outpoint: 10, pos: "-1", duration: null, description: ''}, f)
    })])]
  }
}


export default Bin
