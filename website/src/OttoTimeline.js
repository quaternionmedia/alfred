import m from 'mithril'
import Sortable, { MultiDrag } from 'sortablejs'

// Sortable.mount(new MultiDrag());
var state = require("./Globals").state
import { Video, Edl, array_move } from './Video'
import { Preview } from './Preview'
import { Player } from './Player'
import { auth } from './Login'

export function Clip() {
  // Listeners for an in-progress trim, held so they can be removed again.
  let dragging = null

  return {
    oncreate: vnode => {
      const element = vnode.dom

      element.addEventListener('mousedown', e => {
        // `vnode.attrs`, read now rather than captured at oncreate. This
        // component instance is reused for whatever clip ends up at its
        // position -- the list is unkeyed -- so a reference taken once
        // describes the clip that used to be here.
        const attrs = vnode.attrs

        if (state.tool() == 'trim') {
          e.preventDefault()
          if (dragging) return

          const startWidth = element.getBoundingClientRect().width
          const startX = e.pageX

          const resize = ev => {
            const w = startWidth + (ev.pageX - startX)
            if (w > 4) element.style.width = w + 'px'
          }

          const stop = () => {
            document.removeEventListener('mousemove', resize)
            document.removeEventListener('mouseup', stop)
            dragging = null
            const clip = Edl.edl[attrs.i]
            if (clip) {
              clip.duration = parseFloat(element.style.width) / state.scale()
              Edl.update()
            }
          }

          // On `document`, not on the clip.
          //
          // Both were bound to the element itself, so dragging past its edge
          // -- which is the whole gesture, since the point is to make it
          // wider -- stopped `mousemove` firing, and releasing the button
          // anywhere but over the clip never reached `stopResize`. The
          // `mousemove` handler then stayed attached for the life of the
          // page, and every subsequent press added another.
          //
          // The visible result was that clips resized without being dragged:
          // after pressing two or three of them, moving the pointer across
          // any one resized it, and they appeared to respond in parallel.
          dragging = { resize, stop }
          document.addEventListener('mousemove', resize)
          document.addEventListener('mouseup', stop)
        } else if (state.tool() == 'time') {
          const p = e.offsetX / e.target.offsetWidth
          const within = p * (Number(attrs.duration) || 0)
          // Through the transport, so the viewer follows the click. Setting
          // `Edl.time` directly moved the playhead marker and left the
          // preview showing whatever it had been showing.
          Player.seek(Edl.startOf(attrs.i) + within)
        }
      })
    },

    onremove: () => {
      // A clip removed mid-drag would otherwise leave both handlers on the
      // document, resizing an element that is no longer in the page.
      if (dragging) {
        document.removeEventListener('mousemove', dragging.resize)
        document.removeEventListener('mouseup', dragging.stop)
        dragging = null
      }
    },

    view: vnode => {
      return m(
        '.clip',
        {
          style: {
            width: vnode.attrs.duration * state.scale(),
          },
          ...vnode.attrs,
        },
        [
          m('i.material-icons.progress', {
            style: {
              display: Edl.current == vnode.attrs.i ? 'inherit' : 'none',
              left: Video.time() * state.scale(),
            },
          }),
          ...vnode.children,
        ]
      )
    },
  }
}


/** What a template clip says on the timeline: its text, else its template. */
export const templateLabel = clip => {
  const text = clip && clip.data && clip.data.text
  return text ? String(text) : (clip && clip.name) || 'template'
}

export function Template() {
  return {
    view: vnode =>
      m(
        Clip,
        {
          class: 'template',
          title: `${vnode.attrs.name}: ${templateLabel(vnode.attrs)}`,
          ...vnode.attrs,
        },
        [
          // A label, not an editor. This was a mithril-contenteditable
          // instance, and the version installed (0.1.4) renders two hard-coded
          // "<i>Hello, world</i>" divs before the editable one -- so every
          // template clip read "Hello, world Hello, world" followed by its
          // text, and editing it wrote a stale copy of the text on the next
          // keystroke. The template's settings, text included, are edited
          // beside the preview now (TemplateParams.js), where there is room to
          // show why a setting will not render.
          m('p.clipname', templateLabel(vnode.attrs)),
        ]
      ),
  }
}

export function VideoClip() {
  return {
    view: (vnode) => {
      return m(Clip, vnode.attrs, [
        m('p.clipname', vnode.attrs.name),
        m('p.inpoint', vnode.attrs.inpoint),
        m('p.outpoint', vnode.attrs.outpoint),
      ])
    }
  }
}


export function OttoTimeline() {
  // Which project's clips are currently loaded, so a changed ?project= is
  // noticed. `oninit` alone was not enough: the timeline is mounted at `/`
  // now, so picking a project on the Source stage is a same-document
  // navigation that changes the parameter without remounting anything.
  // Loading only on init meant the first project opened was the only one that
  // ever appeared.
  let loaded = null
  // Which load is the latest. A project id is not enough to tell: opening A,
  // then B, then A again leaves two requests for A in flight, and both used to
  // pass the check -- the second appending A's clips after the first's.
  let ticket = 0

  const open = () => {
    // Only ask for a project when there is one to ask for. Unguarded, this
    // interpolated `undefined` into the path and requested
    // /project/undefined on every visit to the editor without a ?project=
    // parameter -- which the menu link is. The server answered 500 until it
    // was taught to answer 422; either way the request was never meaningful.
    // Normalised before the comparison, not after.
    //
    // `loaded` was set to `projectId || null` while the guard compared the raw
    // `projectId`, so with no ?project= the check was `undefined === null` --
    // false on every pass. `onupdate` runs on every redraw, so the branch
    // below re-ran continuously and cleared `Edl.edl` sixty times a second.
    //
    // The effect was that a timeline with no project selected could not be
    // built at all: a clip added from the media list, or dragged in from the
    // bin, was wiped by the next redraw before it could be seen. It looked
    // like the click had done nothing.
    const projectId = m.route.param('project') || null
    if (projectId === loaded) return
    loaded = projectId
    const mine = ++ticket

    // Empty now, not when the response lands. The previous project's clips
    // are not this one's, and leaving them up while the request is in flight
    // made anything added meanwhile land on the wrong timeline. Not
    // `Edl.update()`: this runs inside a render (oninit, onupdate), where
    // mithril refuses a synchronous redraw.
    Edl.edl = []
    Edl.current = 0
    Edl.time = 0
    m.redraw()

    if (projectId) fetchClips(projectId, mine, 0)
  }

  const fetchClips = (projectId, mine, attempt) =>
    auth(`/project/${projectId}`, {})
      .then(e => {
        // A newer load has started since; it owns the timeline now.
        if (mine !== ticket) return
        // `e.edl` is the API's Edl document, {clips, duration}. This module's
        // `Edl.edl` is the flat clips array -- it is indexed, mapped, sliced
        // and reduced everywhere below. Assigning the document straight in
        // gave `Edl.edl.map is not a function` on every render, which is why
        // the timeline stayed empty even once projects had clips.
        //
        // Same word, two shapes. Worth remembering when reading either side.
        //
        // Anything on the timeline now was added while this request was in
        // flight, to this project, so it goes after the project's clips.
        // Assigning the response outright discarded it: choose a project,
        // add a clip before the fetch returned, and the clip vanished when it
        // did -- then Save, finding nothing on the timeline, saved nothing.
        // That was the save test failing on most runs.
        Edl.edl = ((e.edl && e.edl.clips) || []).concat(Edl.edl)
        Edl.current = 0
        Edl.time = 0
        Edl.update()
      })
      .catch(err => {
        if (mine !== ticket) return
        console.error('could not load the project timeline', err)
        // Try again a few times if the failure might pass, without clearing
        // anything added meanwhile.
        //
        // This used to forget the id instead, so the next redraw asked again
        // -- and every answer redraws, so a project that does not exist was
        // requested in a tight loop for as long as the page stayed open.
        // Missing (404), malformed (422) or unauthorised (401, which auth()
        // has already handled) will not change by asking again.
        const code = err && err.code
        if (code === 401 || code === 404 || code === 422 || attempt >= 3) return
        setTimeout(() => {
          if (mine === ticket) fetchClips(projectId, mine, attempt + 1)
        }, 2000 * (attempt + 1))
      })

  return {
    oninit: open,
    onupdate: open,
    oncreate: (vnode) => {
      new Sortable(vnode.dom, {
        multiDrag: true,
        // Accepts drops from the bin. A bare `'clip'` accepts only its own
        // group, and the bin is `'media'`, so Sortable refused every drag
        // from the bin before the drop handler could see it.
        group: { name: 'clip', put: ['media'] },
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
          Edl.edl = array_move(Edl.edl, e.oldIndex, e.newIndex)
          Edl.update()
          console.log('sorting update', e, Edl.edl)
        },
        removeOnSpill: true,
        onSpill: e => {
          console.log('spilling', e)
          Edl.edl.splice(e.oldIndex, 1)
          Edl.update()
        },
      })
      window.scroll(0,0)
    },
    view: (vnode) => {
      return m('#timeline.timeline', [
        Edl.edl.map((c, i) => {
          if (c) {
            c.i = i
            switch (c.type) {
              case 'template': return m(Template, c)
              case 'video': return m(VideoClip, c)
              // default: return m(Clip, c)
            }
          } else return m('')
        }),
      ])
    }
  }
}
