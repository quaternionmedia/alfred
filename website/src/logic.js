import m from 'mithril'
import { MagnussensFields } from './Form'

import 'regenerator-runtime/runtime'
import { LogicEngine } from 'json-logic-engine'

const engine = new LogicEngine()
engine.addMethod('floor', Math.floor)
engine.addMethod('sqrt', Math.sqrt)

const rules = ({ merge: [
  { eachKey: 
    {
      type: 'video',
      name: 'https://storage.googleapis.com/tower-bucket/alfred/car/Magnussens%20(check%20out%20offer).mp4',
      duration: {var: 'duration'},
      start: 0,
      inpoint: 0,
    }},
    { eachKey: {
      type: 'template',
      name: 'textBox',
      duration: {var: 'duration'},
      start: 17.1,
      data: { eachKey: {
        text: {var: 'carname'},
        color: '#000000',
      //   // textsize: [Math.floor(.9*width), Math.floor(.3*height)],
        font: 'Toyota-Type-Bold',
      //   // fontsize: Math.pow(width*height, .5)/15,
        position: ['center', .1],
        relative: true,
        opacity: 1,
        fxs: {preserve: [{
          name: 'bezier2',
          data: {
            c1x: 1,
            c1y: 0,
            ax: 0,
            ay: 0,
            c2x: 0,
            c2y: 1,
          }
        }]}
      }},
    }},
    { eachKey: {
      type: 'image',
      name: 'https://storage.googleapis.com/tower-bucket/alfred/car/magnussens-screengrab%20logo-fixed-with-toyota.png',
      position: ['center', 'top'],
      // resize: Math.pow(width*height, .5)/3600,
      start: 17.1,
      duration: {var: 'duration'},
    }},
  ]})

const magnussens = engine.build(rules)

let data = {
  carname: 'asdf',
  duration: 15,
  start: 5,
  width: 1920,
  height: 1080,
}

let magForm = {
  carname: 'textBox',
  offerinfo: 'textBox',
  legaltext: 'textBox',
  duration: 30,
  width: 1920,
  height: 1080,
}
console.log('rules', rules)
console.log('magnussens', magnussens, data, MagnussensFields)
console.log('magnussens apply', magnussens(data))

export const Logic = (state, actions) => ({
  view: vnode => m('.logic', {}, [
    m('', {}, JSON.stringify(magnussens(data)))
    // m('.test', {}, 'test')
  ])
})