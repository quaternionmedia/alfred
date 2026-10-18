import m from 'mithril'
import { CaptionsPanel } from '../panels/Captions'
import { Captions } from './store'

/**
 * Where the Captions panel sits until the workspace places it: in the Edit
 * stage, folded to one line so the stage keeps the shape it had -- the
 * timeline, with nothing above the viewer -- until someone opens it.
 *
 * A placement, not part of the panel (contract K3): the workspace registers
 * the panel itself and drops this.
 */

// Open or not, for the visit: leaving the stage and coming back finds it as
// it was left.
const Drawer = { open: false }

export const CaptionsDrawer = {
  view: () => {
    const count = Captions.list.length
    return m('section.captionsdrawer#captions-drawer', [
      m(
        'button.disclosure#captions-toggle',
        {
          'aria-expanded': Drawer.open ? 'true' : 'false',
          'aria-controls': 'panel-captions',
          onclick: () => {
            Drawer.open = !Drawer.open
          },
        },
        [
          m('i.material-icons', Drawer.open ? 'expand_more' : 'chevron_right'),
          `Captions${count ? ` (${count})` : ''}`,
        ]
      ),
      Drawer.open
        ? m('.captionsdrawerbody', { style: { maxHeight: '42vh', display: 'flex' } }, [
            m(CaptionsPanel),
          ])
        : null,
    ])
  },
}
