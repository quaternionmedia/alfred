import m from 'mithril'
import { PanelRegistry } from './registry'

/**
 * Where each panel is drawn: one Mithril root per panel, in a box of its own
 * that a layout places.
 *
 * A panel is mounted into its box (`m.mount`), so `m.redraw()` reaches it
 * wherever the box is -- inside a Golden Layout container or a slot in the
 * phone flow -- and a layout moves the box rather than the panel.
 *
 * That is what lets the layout change without the work changing under it.
 * Golden Layout destroys every component when it loads a layout, and the
 * shell swaps the workspace for the phone flow when the window narrows past
 * the breakpoint: a panel remounted by either would start over -- the
 * timeline would fetch its project again and turn an unsaved edit into a
 * draft to be offered back. So while a layout is being rebuilt (`rebuild`), a
 * box that is lifted out stays drawn, waiting to be placed again; whatever
 * the new layout does not place is erased once it has been built.
 *
 * Otherwise a lifted box is erased: a panel closed, or a stage left in the
 * phone flow, runs its `onremove`, as it did when it was part of the page.
 */

/** @type {Map<string, {id: string, element: HTMLElement, drawn: boolean, attrs: object}>} */
const hosts = new Map()
let rebuilding = false

function hostFor(id) {
  let host = hosts.get(id)
  if (!host) {
    const element = document.createElement('div')
    element.className = `panelhost panelhost--${id}`
    element.dataset.panel = id
    host = { id, element, drawn: false, attrs: {} }
    hosts.set(id, host)
  }
  return host
}

export const PanelHosts = {
  /**
   * Put panel `id`'s box in `slot`, an element the layout owns, with the
   * attributes this layout gives it, and draw it unless told not to yet.
   */
  place(id, slot, { attrs = {}, draw = true } = {}) {
    const host = hostFor(id)
    host.attrs = attrs
    if (host.element.parentElement !== slot) slot.appendChild(host.element)
    if (draw) PanelHosts.draw(id)
    return host.element
  },

  /** Take panel `id`'s box out of its slot. */
  lift(id) {
    const host = hosts.get(id)
    if (!host) return
    host.element.remove()
    if (!rebuilding) PanelHosts.erase(id)
  },

  /** Mount panel `id` in its box, if it is not mounted. */
  draw(id) {
    const host = hostFor(id)
    if (host.drawn) return
    const definition = PanelRegistry.get(id)
    if (!definition) return
    host.drawn = true
    m.mount(host.element, { view: () => m(definition.component, host.attrs) })
  },

  /** Unmount panel `id`, running its `onremove`. */
  erase(id) {
    const host = hosts.get(id)
    if (!host || !host.drawn) return
    host.drawn = false
    m.mount(host.element, null)
  },

  /** Whether panel `id` is mounted. */
  drawn: id => Boolean(hosts.get(id) && hosts.get(id).drawn),

  /**
   * A layout is about to be replaced. Boxes lifted until the new one has
   * been built stay drawn; afterwards, any not placed again are erased.
   */
  rebuild() {
    if (rebuilding) return
    rebuilding = true
    setTimeout(() => {
      rebuilding = false
      for (const host of hosts.values()) {
        if (!host.element.isConnected) PanelHosts.erase(host.id)
      }
    })
  },

  /** The editor is going away: unmount every panel. */
  eraseAll() {
    rebuilding = false
    for (const host of hosts.values()) {
      host.element.remove()
      PanelHosts.erase(host.id)
    }
  },
}
