import m from 'mithril'
import TimelineTools from '../TimelineTools'
import { Scale } from '../Scale'
import { ProjectTools } from '../Tools'
import { SaveState } from '../Autosave'
import { Edl } from '../Video'

/**
 * The timeline's tools, as a panel of their own: the tools that edit the
 * clips and the zoom that scales the lanes, and under them the render button
 * and whether the timeline is saved. Beside the timeline in the workspace, a
 * row above it in the phone flow; the timeline (Timeline.js) keeps the lanes
 * and the bin, and takes its panel's whole width.
 */
export const Tools = {
  view: () =>
    m('section.toolspanel#panel-tools', [
      m('.editortools', [m(TimelineTools), m(Scale)]),
      m('.editoractions', [m(ProjectTools), m(SaveState, { clips: Edl.edl.length })]),
    ]),
}

export default Tools
