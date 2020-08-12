import m from 'mithril'
import { Sortable } from 'sortablejs'
import { VideoClip, Template } from './OttoTimeline'
import { Timeline } from './Timeline'
import { Edl } from './Video'



var Bin = {
  videos: [],
  templates: [],
  oninit: (vnode) => {
    m.request('/videos').then( e => {
      // console.log('got videos!', e)
      Bin.videos = e
    })

    m.request('/templates').then( e => {
      // console.log('got videos!', e)
      Bin.templates = e
    })
  },
  oncreate: vnode => {
    new Sortable(vnode.dom, {
      group: {
        name: 'clip',
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
          e.item.attributes.pos = e.newIndex
          // Timeline.updateEdl()
          // Edl.edl.splice(e.newIndex, 0, [
          var edl = Edl.edl.slice(0, e.newIndex)
          if (clip.type.value == 'template') {
            edl.push({
              name: clip.name.value,
              duration: clip.duration.value,
              type: 'template',
              data: JSON.parse(clip.datastr.value),
            })
          } else {
            edl.push( {
              name: clip.name.value,
              inpoint: Number(clip.inpoint.value),
              outpoint: Number(clip.outpoint.value),
              duration: Number(clip.outpoint.value - clip.inpoint.value),
              description: clip.description.value,
              type: 'video',
            })}
          edl = edl.concat(Edl.edl.slice(e.newIndex))
            console.log('inserted new clip', edl)
            if (e.newIndex <= Edl.current) {
              Edl.current++
            }
          e.item.remove()
          // Timeline.loadEdl(edl)
          Edl.edl = edl
          m.redraw()
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
        Bin.templates.map(clip => {
          // console.log('making template', clip, typeof(clip))
          return m(Template, {...clip, datastr: JSON.stringify(clip.data)})
        }),
        Bin.videos.map(f => {
          return m(VideoClip, {type: 'video', name: f, inpoint: 0, outpoint: 5, pos: "-1", duration: 10, description: ''})
    })])]
  }
}


export default Bin
