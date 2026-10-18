import m from "mithril"
import './styles/editor.scss'
import { Menu } from './Menu'
import { Footer } from './Footer'
import { User } from './User'
import { Head } from './Head'

import Slider from './Slider'
import { PlaybackTools, SpeedTools, ProjectTools } from './Tools'
import { OttoTimeline } from './OttoTimeline'
import { Preview } from './Preview'
import { Resolution, Aspect } from './Resolution'
import Bin from './Bin'
import { Timecode } from './Timecode'

import TimelineTools from './TimelineTools'
import { Scale } from './Scale'
import { StageRail, StagePanel, Flow } from './Stages'
import { TemplateParams } from './TemplateParams'
import { DraftOffer } from './Draft'

export var Otto = {
  // Re-checked on every mount, not only at boot.
  //
  // A single check after boot covered whichever route happened to resolve
  // first and left the others open -- an anonymous visitor reached #!/otto and
  // stayed. This runs on each mount and does nothing until boot has answered.
  oninit: () => User.requireSession(),
  view: (vnode) => {
    /**
     * The timeline is the subject; everything else adorns it.
     *
     * What was here read as a stack of unrelated bars: aspect and resolution
     * pickers floating above the preview, playback controls on their own row,
     * speed and project actions buried inside the timeline's own grid, and the
     * zoom control stranded below it. Related things sat apart and unrelated
     * things sat together, so nothing indicated what acted on what.
     *
     * Three regions now, in the order you work:
     *
     *   viewer   the preview, with output settings beside it -- they describe
     *            what you are looking at
     *   transport playback and speed, together, because both move the playhead
     *   editor   the timeline, flanked by the tools that edit it and the zoom
     *            that scales it, with the bin beneath as its source of clips
     *
     * Each region is one element with one purpose, which is also what lets the
     * appearance tests assert alignment between them.
     */
    return [
      m(Menu),
      m(StageRail),
      // An unsaved timeline kept from before a reload or a new login, offered
      // back -- under the rail, so it is seen whichever stage is open.
      m(DraftOffer),
      m(StagePanel),

      m('section.viewer', [
        m(Head, [m(Preview)]),
        m('.viewersettings', [
          m(Aspect, ['16:9', '4:3', '4:5', '1:1', '5:4', '3:4', '9:16']),
          m(Resolution, ['1080p', '720p', '480p', '240p']),
          // The selected template clip's settings, beside the frame they
          // change. Nothing shows for a media clip.
          m(TemplateParams),
        ]),
      ]),

      m('section.transport', [
        m(Timecode),
        m(Slider),
        m('.transportcontrols', [m(PlaybackTools), m(SpeedTools)]),
      ]),

      m('section.editor', [
        m('.editortools', [m(TimelineTools), m(Scale)]),
        m('.editorsurface', [m(OttoTimeline), m(Bin)]),
        m('.editoractions', [m(ProjectTools)]),
      ]),

      // The editor is the whole app now, so it carries the footer -- which is
      // where the documentation links live since #!/documents was retired.
      m(Footer),
    ]
  },
}


