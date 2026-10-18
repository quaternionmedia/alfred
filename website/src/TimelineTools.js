import m from 'mithril'
import '../node_modules/material-design-icons-iconfont/dist/material-design-icons.css'
import { message } from 'alertifyjs'
import { Edl } from './Video'
import { Player } from './Player'
var state = require("./Globals").state

/**
 * The tools beside the timeline.
 *
 * Seven were offered and three worked. Cut, slip, slide and dual roller set
 * `state.tool()` and nothing read it: the clip handlers knew trim and time,
 * and move was Sortable's. Choosing one highlighted it and then every press
 * on a clip did nothing, which is the worst way for a control to fail.
 *
 * Cut works now. Slip, slide and dual roller are shown disabled, saying so:
 * they are on the way, and hiding them would hide that. Nothing here is a
 * control that silently does nothing.
 */

/** Split the clip under the playhead, or say why not. */
export function cutAtPlayhead() {
  const at = Edl.time
  if (!Edl.edl.length) {
    message('Nothing on the timeline to cut', 3)
    return false
  }
  const second = Edl.cut(at)
  if (second < 0) {
    message('Too close to the start or end of a clip to cut there', 3)
    return false
  }
  // A cut changes the list under Sortable, so the timeline is redrawn from
  // scratch rather than patched (see Edl.update).
  Edl.update()
  // The playhead stays at the cut, on the second half: its start exactly,
  // not `at`, which a pixel position can leave a hair short of it -- on the
  // end of the first half, where the settings shown would be the wrong clip's.
  Player.seek(Edl.startOf(second))
  return true
}

const TOOLS = [
  { id: 'time', label: 'Time', title: 'time selector', glyph: '|' },
  { id: 'trim', label: 'Trim', title: 'trim', glyph: '[ ]' },
  // `swap_horiz`: the icon font has no `swap_horizontal`. The longer name
  // drew the arrow followed by the letters "ontal", and only a fixed-width
  // box clipping them off kept that from showing.
  { id: 'move', label: 'Move', title: 'move', icon: 'swap_horiz' },
  {
    id: 'cut',
    label: 'Cut',
    title: 'cut: click a clip to split it there, or press S to split at the playhead',
    icon: 'content_cut',
  },
  { id: 'slip', label: 'Slip', title: 'slip (not yet available)', icon: 'swap_calls', later: true },
  { id: 'slide', label: 'Slide', title: 'slide (not yet available)', icon: 'sync_alt', later: true },
  {
    id: 'dual roller',
    label: 'Dual roller',
    title: 'dual roller (not yet available)',
    icon: 'compare_arrows',
    later: true,
  },
]

/**
 * One tool: a real button.
 *
 * These were `<i>` icons with `role="button"`, which a screen reader announced
 * as buttons that the keyboard could not reach -- no tab stop, and Enter or
 * Space did nothing. A `<button>` is focusable and answers both keys by
 * itself, so the keyboard gets exactly what the pointer gets.
 *
 * Its name is the tool's (`aria-label`); the icon is decoration, hidden from
 * assistive technology, so it does not announce itself as "content_cut". The
 * title stays as the tooltip, which is where a tool explains how to use it.
 *
 * A tool that is not built yet is `aria-disabled`, not `disabled`: still in
 * the tab order and still pressable, so activating it -- by any means -- says
 * why nothing happened rather than doing nothing silently.
 */
const ToolButton = {
  view: ({ attrs: { tool } }) => {
    const active = !tool.later && state.tool() === tool.id
    return m(
      'button.tool',
      {
        type: 'button',
        title: tool.title,
        'aria-label': tool.label,
        'data-tool': tool.id,
        class: [tool.later ? 'disabled' : '', active ? 'active' : ''].join(' ').trim(),
        'aria-disabled': tool.later ? 'true' : undefined,
        'aria-pressed': tool.later ? undefined : active ? 'true' : 'false',
        onclick: () => {
          if (tool.later) {
            message(`${tool.label} is not available yet`, 3)
            return
          }
          state.tool(tool.id)
        },
      },
      tool.icon
        ? m('i.material-icons', { 'aria-hidden': 'true' }, tool.icon)
        : m('span.glyph', { 'aria-hidden': 'true' }, tool.glyph)
    )
  },
}

export default class TimelineTools {
  view() {
    // A group, not a `toolbar`: that role promises arrow keys moving between
    // the tools, and these are reached with Tab like every other control.
    return m(
      'span#TTools.tools.toolcol',
      { role: 'group', 'aria-label': 'Timeline tools' },
      TOOLS.map(tool => m(ToolButton, { tool }))
    )
  }
}
