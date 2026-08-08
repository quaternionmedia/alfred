import m from 'mithril'
import Sortable, { MultiDrag } from 'sortablejs'
import { ContentEditable } from 'mithril-contenteditable'

// Sortable.mount(new MultiDrag());
var state = require("./Globals").state
import { Video, Edl, array_move } from './Video'
import { Preview } from './Preview'
import { auth } from './Login'

export function Clip() {
  return {
    oncreate: (vnode) => {
      let data = vnode.attrs
      let i = vnode.attrs.i
      let element = vnode.dom
      let original_width = 0;
      let original_x = 0;
      let original_mouse_x = 0;

      element.addEventListener('mousedown', e => {
        if (state.tool() == 'trim') {
          e.preventDefault()
          original_width = parseFloat(getComputedStyle(element, null).getPropertyValue('width').replace('px', ''));
          original_x = element.getBoundingClientRect().left;
          original_mouse_x = e.pageX;

          function resize(e) {
            const w = original_width + (e.pageX - original_mouse_x);
            const dx = e.movementX / state.scale()
            if ((w + dx) > 0)
            element.style.width = w + dx + 'px'
            console.log('trimmed', e, dx, element)
          }
          function stopResize() {
            element.removeEventListener('mousemove', resize)
            Edl.edl[vnode.attrs.i]['duration'] = parseFloat(element.style.width) / state.scale()
            Edl.update()
          }
          element.addEventListener('mousemove', resize)
          element.addEventListener('mouseup', stopResize)

        } else if (state.tool() == 'time') {
          let p = e.offsetX / e.target.offsetWidth
          let d = p * e.target.offsetWidth / state.scale()
          Edl.current = vnode.attrs.i
          Edl.time = d + Edl.durations(Edl.edl.slice(0, vnode.attrs.i))
          Video.clip = data
          Video.time(d)
          console.log('clicked on clip', this, vnode, e, p, d, Edl, Video)
          m.redraw()
        }
      })
    },
    view: (vnode) => {
      return m('.clip', {
        style: {
          width: vnode.attrs.duration*state.scale()
        },
        ...vnode.attrs
        }, [
          m('i.material-icons.progress', {
            style: {
              display: (Edl.current == vnode.attrs.i) ? 'inherit': 'none',
              left: Video.time()*state.scale(),
            }
          }),
          ...vnode.children
        ])
    }
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
    const projectId = m.route.param('project')
    if (projectId === loaded) return
    loaded = projectId || null

    if (!projectId) {
      Edl.edl = []
      Edl.current = 0
      Edl.time = 0
      Edl.update()
      return
    }
    auth(`/project/${projectId}`, {})
        .then(e => {
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
