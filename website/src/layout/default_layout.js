import { PanelRegistry } from './registry'

/**
 * The desktop workspace as it first opens, and as Reset layout restores it.
 *
 *   +------------+------------------------+-------------------+
 *   | Projects   | Viewer                 | Template settings |
 *   |            |                        |                   |
 *   +------------+                        +-------------------+
 *   | Media &    +------------------------+ Render | Deliver  |
 *   | templates  | Timeline               |  | Captions       |
 *   +------------+------------------------+-------------------+
 *
 * The material on the left, the work in the middle -- the picture above the
 * timeline that makes it -- and on the right what is done to the work: the
 * selected clip's settings, and the render, delivery and captions as tabs,
 * Render in front.
 *
 * Every component entry carries `id`, equal to its registry id. A panel is
 * found by `findFirstComponentItemById` -- to bring it forward, or to know it
 * is open rather than open a second -- and an entry without one is invisible
 * to that: codecartographer's canvas could not be brought forward after a
 * draw, and re-opening it would have added another, for exactly this reason.
 * A browser test holds every entry to it.
 */

/** A component entry for registry panel `id`, as every layout names it. */
export function panelConfig(id) {
  const panel = PanelRegistry.get(id)
  if (!panel) throw new Error(`no panel is registered as ${id}`)
  return {
    type: 'component',
    componentType: panel.id,
    id: panel.id,
    title: panel.title,
    isClosable: panel.closable !== false,
  }
}

const stack = (size, ids, active = 0) => ({
  type: 'stack',
  size,
  activeItemIndex: active,
  content: ids.map(panelConfig),
})

/** Settings every layout loads with, saved or default. */
export const LAYOUT_SETTINGS = Object.freeze({
  settings: {
    // Panels are Mithril components bound to this window: a popout window
    // would open empty. So there are none.
    popoutWholeStack: false,
    blockedPopoutsThrowError: false,
    closePopoutsOnUnload: true,
    constrainDragToContainer: true,
    reorderEnabled: true,
    responsiveMode: 'none',
  },
  header: {
    show: 'top',
    popout: false,
    maximise: 'Maximise',
    minimise: 'Restore',
    close: 'Close',
    tabDropdown: 'More panels',
  },
  dimensions: {
    borderWidth: 5,
    borderGrabWidth: 9,
    headerHeight: 28,
    defaultMinItemWidth: '160px',
    defaultMinItemHeight: '96px',
  },
})

export const DEFAULT_LAYOUT = Object.freeze({
  ...LAYOUT_SETTINGS,
  root: {
    type: 'row',
    content: [
      {
        type: 'column',
        size: '22%',
        content: [stack('42%', ['projects']), stack('58%', ['media'])],
      },
      {
        type: 'column',
        size: '50%',
        content: [stack('56%', ['viewer']), stack('44%', ['timeline'])],
      },
      {
        type: 'column',
        size: '28%',
        content: [stack('42%', ['template']), stack('58%', ['render', 'deliver', 'captions'])],
      },
    ],
  },
})

/**
 * Where a closed panel goes back to: as a tab beside the first of `tabs` that
 * is open, or else in a stack of its own above (`before`) or below (`after`)
 * the first of `beside` that is open, in that panel's column. With none of
 * them open, Golden Layout chooses.
 */
export const REOPEN = Object.freeze({
  projects: { tabs: [], beside: ['media'], at: 'before' },
  media: { tabs: [], beside: ['projects'], at: 'after' },
  viewer: { tabs: [], beside: ['timeline'], at: 'before' },
  timeline: { tabs: [], beside: ['viewer'], at: 'after' },
  template: { tabs: [], beside: ['render', 'deliver', 'captions'], at: 'before' },
  render: { tabs: ['deliver', 'captions'], beside: ['template'], at: 'after' },
  deliver: { tabs: ['render', 'captions'], beside: ['template'], at: 'after' },
  captions: { tabs: ['render', 'deliver'], beside: ['template'], at: 'after' },
})
