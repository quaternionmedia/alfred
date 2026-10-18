import { Projects } from '../panels/Projects'
import { Media } from '../panels/Media'
import { Viewer } from '../panels/Viewer'
import { Timeline } from '../panels/Timeline'
import { TemplateSettings } from '../panels/TemplateSettings'
import { Render } from '../panels/Render'
import { Deliver } from '../panels/Deliver'
// The panel is the module's default export, as the captions work (contract
// K3) delivers it; the placeholder exports it under its name as well, and a
// named export is the fallback for a module that has only that.
import * as CaptionsModule from '../panels/Captions'

const Captions = CaptionsModule.default || CaptionsModule.Captions

/**
 * Every panel the editor has, once.
 *
 * The single source of truth for what a panel is called and what draws it, in
 * the manner of codecartographer's panel registry: the desktop workspace
 * registers each with Golden Layout under its id, the default layout places
 * them by id, a saved layout is checked against these ids, and the phone flow
 * stacks the same components. A new panel is an entry here.
 *
 * `id` is also the panel's Golden Layout component type and its item id, so a
 * panel is found -- to show it, or to know it is already open rather than
 * open a second -- by `findFirstComponentItemById(id)`.
 *
 * `stage` is the step of the flow the panel belongs to: `?stage=` brings a
 * stage's panels forward, and choosing a panel's tab says which stage you are
 * on.
 *
 * `whileShown` panels are mounted while they can be seen and not while their
 * tab is behind another, as the stage panels were mounted while their stage
 * was open: what they do on opening -- read the project list again, ask
 * whether a renderer is running, follow unfinished renders -- they do each
 * time they are brought forward. The others are mounted for as long as the
 * panel is in the layout, as the viewer and the timeline were always there.
 *
 * `closable: false` keeps a panel in the layout: the timeline is the work
 * itself, and closing it by accident is not an arrangement anyone wants.
 *
 * @typedef {object} PanelDefinition
 * @property {string} id
 * @property {string} title
 * @property {'source' | 'edit' | 'render' | 'deliver'} stage
 * @property {import('mithril').Component} component
 * @property {boolean} [whileShown]
 * @property {boolean} [closable]
 */

/** @type {readonly PanelDefinition[]} */
const PANELS = Object.freeze([
  { id: 'projects', title: 'Projects', stage: 'source', component: Projects, whileShown: true },
  { id: 'media', title: 'Media & templates', stage: 'source', component: Media, whileShown: true },
  { id: 'viewer', title: 'Viewer', stage: 'edit', component: Viewer },
  { id: 'timeline', title: 'Timeline', stage: 'edit', component: Timeline, closable: false },
  { id: 'template', title: 'Template settings', stage: 'edit', component: TemplateSettings },
  { id: 'render', title: 'Render', stage: 'render', component: Render, whileShown: true },
  { id: 'deliver', title: 'Deliver', stage: 'deliver', component: Deliver, whileShown: true },
  { id: 'captions', title: 'Captions', stage: 'edit', component: Captions, whileShown: true },
])

export const PanelRegistry = {
  /** @returns {readonly PanelDefinition[]} */
  all: () => PANELS,
  /** @returns {PanelDefinition | undefined} */
  get: id => PANELS.find(panel => panel.id === id),
  /** @returns {string[]} */
  ids: () => PANELS.map(panel => panel.id),
}

/**
 * The panels a stage brings forward, the one it is about first.
 *
 * `?stage=source` shows the project list and the library, `?stage=edit` the
 * timeline and the viewer, and Render and Deliver their own panels.
 */
export const STAGE_PANELS = Object.freeze({
  source: ['projects', 'media'],
  edit: ['timeline', 'viewer'],
  render: ['render'],
  deliver: ['deliver'],
})
