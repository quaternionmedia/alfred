import m from 'mithril'
import { Sortable } from 'sortablejs'
import { VideoClip, Template } from './OttoTimeline'
import { Edl } from './Video'
import { auth } from './Login'
import { User } from './User'


var Bin = {
  videos: [],
  templates: [],
  loaded: false,

  // Fetch once a session exists, and not before.
  //
  // Two reasons this is not just `oninit`. The timeline is mounted at `/` now,
  // so an anonymous visitor lands on it -- and these calls each answered 401
  // and each raised an alertify "not authorized" toast, so the login page
  // arrived wearing two error notices it had not earned. And a restored
  // session resolves asynchronously, so `oninit` can run before `loggedIn` is
  // true; loading only there left the bin permanently empty for anyone who
  // arrived by reload rather than by logging in.
  fill: () => {
    if (Bin.loaded || !User.loggedIn) return
    Bin.loaded = true

    // `m.request` here, not `auth`, meant no Authorization header on a route
    // that requires one -- so /videos answered 401 every time and the media
    // bin was permanently empty. Nothing surfaced it: the rejection was never
    // handled, so the bin simply rendered nothing.
    auth('/videos')
      .then(e => {
        Bin.videos = e
        m.redraw()
      })
      .catch(e => {
        Bin.loaded = false
        console.error('could not load videos for the bin', e)
      })

    auth('/templates')
      .then(e => {
        Bin.templates = e
        m.redraw()
      })
      .catch(e => {
        Bin.loaded = false
        console.error('could not load templates for the bin', e)
      })
  },

  oninit: () => Bin.fill(),
  onupdate: () => Bin.fill(),
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
          e.item.attributes.pos = e.newIndex
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
