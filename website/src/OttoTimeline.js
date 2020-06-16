import m from 'mithril'
import { Sortable, MultiDrag } from 'sortablejs'
import { ContentEditable } from 'mithril-contenteditable'

Sortable.mount(new MultiDrag());
// var Clip = require('./Clip').Clip
import Clip from './Clip'
var state = require("./Globals").state
import { Video, Edl } from './Video'
import { Preview } from './Preview'

function array_move(arr, old_index, new_index) {
    let element = arr[old_index];
    arr.splice(old_index, 1);
    arr.splice(new_index, 0, element);
    return arr
};


export function Template() {
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
          Edl.current = i
          Edl.time = d + Edl.durations(Edl.edl.slice(0, i))
          console.log('clicked on clip', this, vnode, e, p, d, Edl)
          Video.clip = data
          Video.time = d
          m.redraw()

        }
      })

    },
    view: (vnode) => {

      if (vnode.attrs.type == 'template') {
        return m('.clip', {
            style: {
              width: vnode.attrs.duration*state.scale()
            },
          }, [
              m('p', `${vnode.attrs.i} ${vnode.attrs.name} ${JSON.stringify(vnode.attrs.data)}`),
              m(ContentEditable, {
                // Original HTML input
                html: state.html,
                // Returns the updated HTML code
                onchange: html => {
                  state.html = html;
                  console.log(html);
                },
                // Example to prevent the user from entering commas
                onkeydown: e => {
                  if (e.key === ',') {
                    e.preventDefault();
                  }
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
              m('i.progress', {
                style: {
                  display: (Edl.current == vnode.attrs.i) ? 'inherit': 'none',
                  left: Video.time * state.scale(),
                }
              })
            ]
          )
      } else {
        return m('.clip', {style: {
          width: vnode.attrs.duration*state.scale()
        },}, [
          m('p#i.i', vnode.attrs.i),
          m('p#clipname.clipname', vnode.attrs.filename),
          m('p#inpoint.inpoint', vnode.attrs.inpoint),
          m('p#outpoint.outpoint', vnode.attrs.outpoint),
          m('i.material-icons.progress', {
            style: {
              display: (Edl.current == i) ? 'inherit': 'none',
              left: Video.time*state.scale(),
            }
          })
        ])
      }


    }
  }
}

export function OttoTimeline() {
  return {
    oninit: (vnode) => {
      m.request('/otto').then(e => {
        console.log('got otto', e)
        Edl.edl = e
      })
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
  },
    view: (vnode) => {
      return m('#timeline.timeline', [
        Edl.edl.map((c, i) => {
          if (c) {
            c.i = i
            return m(Template, c)
          } else return m('')
        })
      ])
    },
  }
}
