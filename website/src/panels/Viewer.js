import m from 'mithril'
import { Head } from '../Head'
import { Preview } from '../Preview'
import { Aspect, Resolution } from '../Resolution'
import { Timecode } from '../Timecode'
import Slider from '../Slider'
import { PlaybackTools, SpeedTools } from '../Tools'

/**
 * The viewer: the frame, the output it is drawn at, and the transport.
 *
 * Two of the editor's three regions, as one panel (the timeline is the third,
 * Timeline.js). What each holds is as it was when the editor was one page:
 *
 *   viewer    the preview, with output settings beside it -- they describe
 *             what you are looking at
 *   transport playback and speed, together, because both move the playhead
 *
 * `settings`, when a layout gives it, draws what goes beside the output
 * settings. The phone flow puts the selected template clip's settings there,
 * where they always were; the desktop workspace gives them a panel of their
 * own.
 */

/**
 * What is drawn over the picture: components, each in the frame after the
 * preview, in front of it. The frame is positioned (`position: relative`,
 * editor.scss) and the preview fills it, so an overlay places itself over
 * the picture with `position: absolute`. Empty here; the captions work adds
 * the caption under the playhead -- `viewerOverlays.push(CaptionOverlay)` --
 * without the viewer changing shape.
 *
 * @type {import('mithril').Component[]}
 */
export const viewerOverlays = []

export const Viewer = {
  view: ({ attrs }) =>
    m('.viewerpanel', [
      m('section.viewer', [
        // The frame fits the room this panel is given, at the output's
        // aspect ratio (Head.js), so it is wrapped in the room to fit.
        m(
          '.viewerframe',
          m(Head, [m(Preview), viewerOverlays.map(overlay => m(overlay))])
        ),
        m('.viewersettings', [
          m(Aspect, ['16:9', '4:3', '4:5', '1:1', '5:4', '3:4', '9:16']),
          m(Resolution, ['1080p', '720p', '480p', '240p']),
          typeof attrs.settings === 'function' ? attrs.settings() : null,
        ]),
      ]),

      m('section.transport', [
        m(Timecode),
        m(Slider),
        m('.transportcontrols', [m(PlaybackTools), m(SpeedTools)]),
      ]),
    ]),
}

export default Viewer
