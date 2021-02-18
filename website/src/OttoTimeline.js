import m from 'mithril'
import Sortable, { MultiDrag } from 'sortablejs'
import { ContentEditable } from 'mithril-contenteditable'

// Sortable.mount(new MultiDrag());
var state = require("./Globals").state
import { Video, Edl, array_move } from './Video'
import { Preview } from './Preview'


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
            this.html = `${JSON.stringify(vnode.attrs.data['text']).slice(1, -1)}`
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
        m('p#clipname.clipname', vnode.attrs.name),
        m('p#inpoint.inpoint', vnode.attrs.inpoint),
        m('p#outpoint.outpoint', vnode.attrs.outpoint),
      ])
    }
  }
}


export function OttoTimeline() {
  return {
    oninit: (vnode) => {
      m.request(`/project/${m.route.param('project')}`, {}).then(e => {
        console.log('got otto', e)
        Edl.edl = e.edl
        Edl.current = 0
        Edl.time = 0
        Edl.update()
      })
    },
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
