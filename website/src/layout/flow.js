import m from 'mithril'
import './flow.scss'
import { PanelRegistry } from './registry'
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

/** One panel from the registry, in a box the flow's stylesheet places. */
const panel = (id, attrs, key) => {
  const definition = PanelRegistry.get(id)
  return m(
    `.flowpanel.flowpanel--${id}`,
    key ? { key: id } : {},
    m(definition.component, attrs || {})
  )
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
      (FLOW_STAGE_PANELS[Flow.stage()] || []).map(id => panel(id, null, true))
    ),
    panel('viewer', {
      settings: m(PanelRegistry.get('template').component, { quiet: true }),
    }),
    panel('timeline'),
    // The editor is the whole app, so it carries the footer -- which is where
    // the documentation links and the session link live.
    m(Footer),
  ],
}
