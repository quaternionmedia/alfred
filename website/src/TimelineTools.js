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
  { id: 'time', title: 'time selector', glyph: '|' },
  { id: 'trim', title: 'trim', glyph: '[ ]' },
  { id: 'move', title: 'move', icon: 'swap_horizontal' },
  {
    id: 'cut',
    title: 'cut: click a clip to split it there, or press S to split at the playhead',
    icon: 'content_cut',
  },
  { id: 'slip', title: 'slip (not yet available)', icon: 'swap_calls', later: true },
  { id: 'slide', title: 'slide (not yet available)', icon: 'sync_alt', later: true },
  {
    id: 'dual roller',
    title: 'dual roller (not yet available)',
    icon: 'compare_arrows',
    later: true,
  },
]

export default class TimelineTools {
  view() {
    return m(
      'span#TTools.tools.toolcol',
      {},
      TOOLS.map(tool =>
        m(
          tool.icon ? 'i.material-icons' : 'i.custom',
          {
            title: tool.title,
            'data-tool': tool.id,
            // A button to assistive technology, so that pressed and disabled
            // are announced: on a bare <i> neither attribute means anything.
            role: 'button',
            class: tool.later ? 'disabled' : '',
            'aria-disabled': tool.later ? 'true' : undefined,
            'aria-pressed': tool.later ? undefined : state.tool() === tool.id ? 'true' : 'false',
            onclick: () => {
              if (tool.later) {
                message(`${tool.id[0].toUpperCase()}${tool.id.slice(1)} is not available yet`, 3)
                return
              }
              state.tool(tool.id)
            },
            style: {
              'background-color': state.tool() === tool.id ? '#393939' : 'transparent',
            },
          },
          tool.icon || tool.glyph
        )
      )
    )
  }
}
