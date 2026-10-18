import m from 'mithril'
import './golden-layout.css'
import './workspace.scss'
import { StackedFlow } from './flow'
import { PanelHosts } from './hosts'
import { PanelsMenu } from './PanelsMenu'
import { Workspace } from './workspace'
import { StageRail } from '../Stages'
import { DraftOffer } from '../Draft'
import { Menu } from '../Menu'
import { Footer } from '../Footer'

/**
 * Where the workspace starts: 1024 CSS pixels wide.
 *
 * Three columns -- the material, the viewer over the timeline, and what is
 * done to the work -- give the middle one about half the width, and below
 * 1024 that is under 512 pixels: too narrow for a timeline worth arranging
 * beside a library and the inspector, and a 16:9 frame in it would be under
 * 300 pixels tall. 1024 is also where a tablet turned sideways begins, so a
 * tablet held that way gets the workspace, held upright (768-834) the flow,
 * and a phone the flow. (The editor's own grid gives way at 820, and the
 * header's menu turns into a drawer at 1026 -- it holds no links, so the two
 * pixels between are of no consequence.)
 */
export const WIDE = '(min-width: 1024px)'

const wide = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(WIDE) : null
const redraw = () => m.redraw()

/** The desktop page: the header, the rail with the Panels menu, the dock. */
const WorkspacePage = {
  view: () => [
    m(Menu),
    m('.workbar', [m(StageRail), m(PanelsMenu)]),
    // An unsaved timeline kept from before a reload or a new login, offered
    // back above every panel, so it is seen whichever is in front.
    m(DraftOffer),
    m('.workspace#workspace', {
      oncreate: ({ dom }) => Workspace.create(dom),
      onupdate: () => Workspace.followRoute(),
      onremove: () => Workspace.destroy(),
    }),
    m(Footer),
  ],
}

/**
 * The editor's page: the workspace on a wide screen, the stage flow on a
 * narrow one, built from the same panels (registry.js).
 *
 * Crossing the breakpoint swaps one for the other without starting a panel
 * over (hosts.js): the timeline, the frame in the viewer and what is typed in
 * a field are where they were.
 */
export const Shell = () => {
  let mode = null
  return {
    oncreate: () => {
      if (wide) wide.addEventListener('change', redraw)
    },
    onremove: () => {
      if (wide) wide.removeEventListener('change', redraw)
      // The editor is going: every panel runs its `onremove`, as the page's
      // parts did -- an unsaved timeline is kept, the viewer lets go.
      PanelHosts.eraseAll()
    },
    view: () => {
      const next = wide && wide.matches ? 'workspace' : 'flow'
      if (mode && next !== mode) PanelHosts.rebuild()
      mode = next
      return next === 'workspace' ? m(WorkspacePage) : m(StackedFlow)
    },
  }
}
