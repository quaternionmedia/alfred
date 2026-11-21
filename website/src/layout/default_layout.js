import { PanelRegistry } from './registry'

/**
 * The desktop workspace as it first opens, and as Reset layout restores it.
 *
 *   +------------+------------------------+-------------------+
 *   | Projects   | Viewer                 | Template settings |
 *   |  | Drafts  |                        |  | Transcript     |
 *   +------------+                        +-------------------+
 *   | Media      |-------+----------------+ Render | Deliver  |
 *   +------------+ Tools | Timeline       |  | Captions       |
 *   | Templates  |       |                |                   |
 *   |  | Recipes |       |                |                   |
 *   +------------+-------+----------------+-------------------+
 *
 * The material on the left, the files above the templates, with the drafts
 * a recipe left as a tab beside the projects they are and the recipes as a
 * tab beside the templates; the work in the
 * middle -- the picture above the timeline that makes it, with the tools
 * that act on the timeline beside it -- and on the right what is done to the work: the
 * selected clip's settings with the transcript, and the render, delivery
 * and captions as tabs, Render in front. (A fourth tab below would overflow
 * into its menu at 1200 px.)
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

/** Stacks side by side, each with its share of the row. */
const row = (size, stacks) => ({ type: 'row', size, content: stacks })

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
        content: [
          stack('34%', ['projects', 'drafts']),
          stack('36%', ['media']),
          stack('30%', ['templates', 'recipes']),
        ],
      },
      {
        type: 'column',
        size: '50%',
        content: [
          stack('56%', ['viewer']),
          // The tools' column is two buttons wide; the timeline takes the rest.
          row('44%', [stack('18%', ['tools']), stack('82%', ['timeline'])]),
        ],
      },
      {
        type: 'column',
        size: '28%',
        content: [stack('42%', ['template', 'transcript']), stack('58%', ['render', 'deliver', 'captions'])],
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
  projects: { tabs: ['drafts'], beside: ['media', 'templates'], at: 'before' },
  drafts: { tabs: ['projects'], beside: ['media', 'templates'], at: 'before' },
  media: { tabs: [], beside: ['projects', 'templates'], at: 'after' },
  templates: { tabs: ['recipes'], beside: ['media', 'projects'], at: 'after' },
  recipes: { tabs: ['templates'], beside: ['media', 'projects'], at: 'after' },
  viewer: { tabs: [], beside: ['timeline', 'tools'], at: 'before' },
  timeline: { tabs: [], beside: ['viewer'], at: 'after' },
  tools: { tabs: [], beside: ['timeline', 'viewer'], at: 'after' },
  template: { tabs: ['transcript'], beside: ['render', 'deliver', 'captions'], at: 'before' },
  render: { tabs: ['deliver', 'captions'], beside: ['template', 'transcript'], at: 'after' },
  deliver: { tabs: ['render', 'captions'], beside: ['template', 'transcript'], at: 'after' },
  captions: { tabs: ['render', 'deliver'], beside: ['template', 'transcript'], at: 'after' },
  transcript: { tabs: ['template'], beside: ['render', 'deliver', 'captions'], at: 'before' },
})
