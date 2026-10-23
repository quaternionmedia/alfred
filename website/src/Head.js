import m from 'mithril'
var state = require("./Globals").state

/**
 * The viewer's frame: the output's aspect ratio, sized to the window.
 *
 * In pixels. These were bare numbers -- `width: 640` -- which only quirks mode
 * reads as a length; the page had no doctype, so it was in quirks mode, and
 * giving it one (so that phones lay it out to standard) would otherwise have
 * left the frame without a width at all.
 */
const frame = () => {
  const landscape = window.innerWidth > window.innerHeight
  const share = landscape ? 0.4 : 0.24
  return {
    width: `${(state.width() / state.height()) * window.innerHeight * share}px`,
    height: landscape ? '40vh' : '24vh',
  }
}

export function Head() {
  // A listener, not `window.onresize = ...`, which replaced whatever else had
  // claimed the window's resize -- and was never released.
  const resize = () => m.redraw()
  return {
    oncreate: () => window.addEventListener('resize', resize),
    onremove: () => window.removeEventListener('resize', resize),
    view: vnode => m('#head.head', { style: frame(), ...vnode.attrs }, vnode.children),
  }
}
