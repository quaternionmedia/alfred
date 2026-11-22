import m from 'mithril'
import { OttoTimeline } from '../OttoTimeline'
import { Lanes } from '../lanes/Lanes'
import Bin from '../Bin'

/**
 * The timeline, with the bin beneath as its source of clips -- the editor
 * region, as one panel. The clips are one lane of several (Lanes.js): the
 * ruler above them, and the words, the sound, the effects and the cues under
 * them, all at one scale. The tools that edit it and the zoom that scales it
 * are a panel of their own (Tools.js), so the lanes take this one's width.
 *
 * The bin stays under the timeline it feeds: that is the direction clips are
 * dragged. Where the Media panel or the Templates panel is showing, it is
 * the one list of the same things, and the bin steps aside.
 */
export const Timeline = {
  view: () =>
    m('section.editor', [
      m('.editorsurface', [m(Lanes, m(OttoTimeline)), Bin.listed ? null : m(Bin)]),
    ]),
}

export default Timeline
