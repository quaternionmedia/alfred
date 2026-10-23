import m from 'mithril'
var state = require("./Globals").state

/**
 * The viewer's frame: the output's aspect ratio, as large as fits the room it
 * is given.
 *
 * It was sized from the window -- 40% of its height, or 24% upright -- which
 * suited one page and no panel: in the desktop workspace the viewer is a
 * panel the viewer can make any size, and a frame sized from the window
 * either spilled out of it or left it mostly empty, and stopped being the
 * output's shape whenever the row stretched it. Now the frame measures its
 * room -- the element it is placed in -- and is the largest rectangle of the
 * output's aspect that fits, so dragging a splitter resizes the picture and
 * never reshapes it. The phone flow gives the frame the room it always had
 * (editor.scss).
 *
 * In pixels: a bare number is a length only in quirks mode, and the page has
 * a doctype.
 */

/** The largest `aspect` rectangle inside `room`, or nothing before it is measured. */
export function fit(room, aspect) {
  if (!room || !(room.width > 0) || !(room.height > 0) || !(aspect > 0)) return null
  const width = Math.min(room.width, room.height * aspect)
  return { width: Math.floor(width), height: Math.floor(width / aspect) }
}

export function Head() {
  let room = null
  let observer = null

  const measure = element => {
    const { width, height } = element.getBoundingClientRect()
    const changed = !room || Math.abs(room.width - width) >= 1 || Math.abs(room.height - height) >= 1
    room = { width, height }
    return changed
  }

  return {
    oncreate: vnode => {
      const parent = vnode.dom.parentElement
      if (!parent) return
      measure(parent)
      m.redraw()
      // A listener on the window covered the page's resizing and none of a
      // panel's: the room changes when a splitter moves, too.
      observer = new ResizeObserver(() => {
        if (measure(parent)) m.redraw()
      })
      observer.observe(parent)
    },
    onremove: () => {
      if (observer) observer.disconnect()
      observer = null
    },
    view: vnode => {
      const size = fit(room, state.width() / state.height())
      const style = size
        ? { width: `${size.width}px`, height: `${size.height}px` }
        : { width: '100%', height: 'auto', aspectRatio: `${state.width()} / ${state.height()}` }
      return m('#head.head', { style, ...vnode.attrs }, vnode.children)
    },
  }
}
