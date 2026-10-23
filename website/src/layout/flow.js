import m from 'mithril'
import './flow.scss'
import { PanelRegistry } from './registry'
import { PanelHosts } from './hosts'
import { Flow, StageRail } from '../Stages'
import { DraftOffer } from '../Draft'
import { Menu } from '../Menu'
import { Footer } from '../Footer'

/**
 * What each stage puts above the viewer in the phone flow.
 *
 * Edit had nothing of its own -- it *is* the timeline -- and is where the
 * captions are edited, the one thing about a timeline that is written rather
 * than arranged.
 */
export const FLOW_STAGE_PANELS = Object.freeze({
  source: ['projects', 'media'],
  edit: ['captions'],
  render: ['render'],
  deliver: ['deliver'],
})

/**
 * A place in the flow for one panel from the registry.
 *
 * The panel is drawn in a box of its own (hosts.js) that this slot holds, so
 * it is the same panel the workspace showed -- the flow and the workspace
 * swap at the breakpoint without starting it over. A slot that goes, as a
 * stage's panels do when another stage is chosen, takes its panel's box with
 * it, and the panel runs its `onremove` as it did when it was part of the
 * page.
 */
const Slot = {
  oncreate: ({ dom, attrs }) => PanelHosts.place(attrs.panel, dom, { attrs: attrs.with || {} }),
  onupdate: ({ dom, attrs }) => PanelHosts.place(attrs.panel, dom, { attrs: attrs.with || {} }),
  onremove: ({ attrs }) => PanelHosts.lift(attrs.panel),
  view: ({ attrs }) => m(`.flowpanel.flowpanel--${attrs.panel}`),
}

/**
 * The stage flow: one stage at a time, over the viewer and the timeline.
 *
 * Source -> Edit -> Render -> Deliver, chosen on the rail, with the viewer and
 * the timeline always below them -- the editor as it is on a phone, and on
 * anything too narrow for the workspace (shell.js). Built from the same panel
 * modules as the workspace: the stage's panels from FLOW_STAGE_PANELS, then
 * the viewer with the selected template clip's settings beside the output
 * settings, where they always were, then the timeline.
 */
export const StackedFlow = {
  view: () => [
    m(Menu),
    m(StageRail),
    // An unsaved timeline kept from before a reload or a new login, offered
    // back -- under the rail, so it is seen whichever stage is open.
    m(DraftOffer),
    m(
      '.flowstage',
      (FLOW_STAGE_PANELS[Flow.stage()] || []).map(id => m(Slot, { key: id, panel: id }))
    ),
    m(Slot, {
      panel: 'viewer',
      with: { settings: () => m(PanelRegistry.get('template').component, { quiet: true }) },
    }),
    m(Slot, { panel: 'timeline' }),
    // The editor is the whole app, so it carries the footer -- which is where
    // the documentation links and the session link live.
    m(Footer),
  ],
}
