import m from "mithril"
import { Head } from './Head'

import Slider from './Slider'
import { Timeline } from './Timeline'
import { PlaybackTools, SpeedTools, ProjectTools } from './Tools'
import { OttoTimeline } from './OttoTimeline'
import { Preview } from './Preview'
import { Resolution, Aspect } from './Resolution'
import Bin from './Bin'
import { Timecode } from './Timecode'

import TimelineTools from './TimelineTools'
import { Scale } from './Scale'

export var Otto = {
  view: (vnode) => {
    return [
      m(Head, [
        m(Preview)
      ]),
      m('.fit.center', {}, [
        m(Aspect, [
          '16:9',
          '4:3',
          '4:5',
          '1:1',
          '5:4',
          '3:4',
          '9:16'
        ]),
        m(Resolution, [
          '1080p',
          '720p',
          '480p',
          '240p',
        ]),
      ]),
      m(PlaybackTools),
      m('.bar.fullwidth.timelinegrid', {}, [
        m(TimelineTools),
        m('.vcenter', {}, [
          m('.bar', {}, [
            m(Timecode),
            m(Slider),
          ]),
          m('.bar.right', {}, [
            m(SpeedTools),
            m('.right', {}, [
              m(ProjectTools),
            ]),
          ]),
          m(OttoTimeline),
        ]),
      ]),
      m(Scale),
      m('.spacer', {style:{height:'3em'}}, []),
      // m(Bin),
    ]
  }
}

