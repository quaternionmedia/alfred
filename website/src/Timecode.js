import m from 'mithril'
import { Edl } from './Video'
const formatTime = require('./Slider').formatTime

export function Timecode() {
  return {
    view: vnode => {
      return m('p.timecode', {}, formatTime(Edl.time))
    }
  }
}
