import m from 'mithril'
import TimelineTools from '../TimelineTools'
import { Scale } from '../Scale'
import { OttoTimeline } from '../OttoTimeline'
import Bin from '../Bin'
import { ProjectTools } from '../Tools'

/**
 * The timeline, flanked by the tools that edit it and the zoom that scales
 * it, with the bin beneath as its source of clips -- the editor region of
 * the page it used to be, as one panel.
 *
 * The bin stays under the timeline it feeds: that is the direction clips are
 * dragged, and the Media & templates panel (Media.js) is the readable list of
 * the same things, wherever it is placed.
 */
export const Timeline = {
  view: () =>
    m('section.editor', [
      m('.editortools', [m(TimelineTools), m(Scale)]),
      m('.editorsurface', [m(OttoTimeline), m(Bin)]),
      m('.editoractions', [m(ProjectTools)]),
    ]),
}

export default Timeline
