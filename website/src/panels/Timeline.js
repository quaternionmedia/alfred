import m from 'mithril'
import TimelineTools from '../TimelineTools'
import { Scale } from '../Scale'
import { OttoTimeline } from '../OttoTimeline'
import Bin from '../Bin'
import { ProjectTools } from '../Tools'
import { SaveState } from '../Autosave'
import { Edl } from '../Video'

/**
 * The timeline, flanked by the tools that edit it and the zoom that scales
 * it, with the bin beneath as its source of clips -- the editor region, as
 * one panel.
 *
 * The bin stays under the timeline it feeds: that is the direction clips are
 * dragged. Where the Media & templates panel (Media.js) is showing, it is the
 * one list of the same things, and the bin steps aside.
 */
export const Timeline = {
  view: () =>
    m('section.editor', [
      m('.editortools', [m(TimelineTools), m(Scale)]),
      m('.editorsurface', [m(OttoTimeline), Bin.listed ? null : m(Bin)]),
      m('.editoractions', [m(ProjectTools), m(SaveState, { clips: Edl.edl.length })]),
    ]),
}

export default Timeline
