import m from 'mithril'
import Sortable, { MultiDrag } from 'sortablejs'
import { ContentEditable } from 'mithril-contenteditable'

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


export function Template() {
  return {
    view: (vnode) => {
      return m(Clip, {
          class: 'template',
          ...vnode.attrs,
        }, [
        m(ContentEditable, {
          style: {margin: '5px'},
          // Original HTML input
          html: this.html,
          // Returns the updated HTML code
          oncreate: html => {
            // The same Template component renders both timeline clips and bin
            // entries, and only timeline clips carry `data`. Bin entries come
            // from /templates and describe a template rather than an instance
            // of one, so this threw "Cannot read properties of undefined
            // (reading 'text')" on every render of the bin.
            //
            // Falling back to the template's name gives a bin entry a sensible
            // label instead of an exception.
            const data = vnode.attrs.data || {}
            const label = data['text'] !== undefined ? data['text'] : vnode.attrs.name
            this.html = `${JSON.stringify(label === undefined ? '' : label).slice(1, -1)}`
            m.redraw()
          },
          onchange: html => {
            this.html = html

          },
          // Example to prevent the user from entering commas
          onkeydown: e => {
            switch (e.key) {
              case 'Enter': e.preventDefault()
              e.stopPropagation()
              console.log('enter')
              Edl.update()
              case 'ArrowLeft': e.stopPropagation()
              case 'ArrowRight': e.stopPropagation()
            }
            Edl.edl[vnode.attrs.i].data['text'] = this.html
          },

          // Replace the base tag, if needed
          tagName: 'div',
          // By default, &amp; etc are replaced by their normal counterpart when losing focus.
          // cleanupHtml: false,
          // By default, don't allow the user to enter newlines
          // preventNewline: false,
          // By default, select all text when the element receives focus
          // selectAllOnFocus: false,
          // By default, when pasting text, remove all HTML and keep the plain text.
          // pasteAsPlainText: false,
        }),
      ])
    }
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

    if (!projectId) {
      Edl.edl = []
      Edl.current = 0
      Edl.time = 0
      Edl.update()
      return
    }
    // Remember which request this is, so a slow one cannot overwrite newer
    // state when it finally lands. Without this, selecting a project and
    // adding material before the fetch returned discarded the addition: the
    // response assigns the whole clip list, and it assigned the version from
    // before the click.
    const pending = projectId
    auth(`/project/${projectId}`, {})
        .then(e => {
          if (pending !== loaded) return
          // `e.edl` is the API's Edl document, {clips, duration}. This module's
          // `Edl.edl` is the flat clips array -- it is indexed, mapped, sliced
          // and reduced everywhere below. Assigning the document straight in
          // gave `Edl.edl.map is not a function` on every render, which is why
          // the timeline stayed empty even once projects had clips.
          //
          // Same word, two shapes. Worth remembering when reading either side.
          Edl.edl = (e.edl && e.edl.clips) || []
          Edl.current = 0
          Edl.time = 0
          Edl.update()
        })
        .catch(err => {
          // Let the next attempt retry rather than pinning a failed id.
          loaded = null
          console.error('could not load the project timeline', err)
        })
  }

  return {
    oninit: open,
    onupdate: open,
    oncreate: (vnode) => {
      new Sortable(vnode.dom, {
        multiDrag: true,
        group: 'clip',
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
