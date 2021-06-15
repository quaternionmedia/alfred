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
      name: 'makeColor',
      duration: 7.2,
      start: 17.1,
      data: {preserve: {
        color: [255,255,255],
        opacity: 1,
      }}
    }},
    { eachKey: {
      type: 'image',
      name: 'https://storage.googleapis.com/tower-bucket/alfred/car/magnussens-screengrab%20logo-fixed-with-toyota.png',
      position: ['center', 'top'],
      resize: {'/': [{sqrt: {'*': [{var: 'width'}, {var: 'height'}]}}, 3600]},
      start: 17.1,
      duration: 7.2,
    }},
    { eachKey: {
      type: 'template',
      name: 'textBox',
      duration: 7.2,
      start: 17.1,
      // relative: false,
      data: { eachKey: {
        text: {var: 'carname'},
        color: '#EB0A1E',
        // color: '#000000',
      //   // textsize: [Math.floor(.9*width), Math.floor(.3*height)],
      textsize: [{floor: {'*': [.9, {var: 'width'}]}}, {floor: {'*': [.3, {var: 'height'}]}}],
        font: 'Toyota-Type-Bold',
      //   // fontsize: Math.pow(width*height, .5)/15,
        fontsize: {'/': [{sqrt: {'*': [{var: 'width'}, {var: 'height'}]}}, 15]},
        // fontsize: {'/': [{var: 'width'}, {var: 'height'}]},
        // position: [.9, .3],
        // relative: true,
        // position: 'center',
        position: ['center', {floor: {'*': [.1, {var: 'height'}]}}],
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
      type: 'template',
      name: 'textBox',
      duration: 7.2,
      start: 17.1,
      // position: [.5, .8 ],
      relative: true,
      data: {eachKey: {
        color: '#EB0A1E',
        text: {var: 'offerinfo'},
        textsize: [{floor: {'*': [.9, {var: 'width'}]}}, {floor: {'*': [.5, {var: 'height'}]}}],
        // textsize: [1000, 1000],
        font: 'Toyota-Type',
        fontsize: {'/': [{sqrt: {'*': [{var: 'width'}, {var: 'height'}]}}, 32]},
        opacity: 1,
        position: 'center',
        // align: data.offeralign == 'left' ? 'west' : data.offeralign,
        align: {if: [{'==': [{var: 'offeralign'}, 'left']}, 'west', {var: 'offeralign'}]},
      }},
    },},
    { eachKey: {
      type: 'template',
      name: 'textBox',
      duration: 7.2,
      start: 17.1,
      data: { eachKey: {
        color: '#333333',
        text: {var: 'legaltext'},
        method: 'caption',
        textsize: [{floor: {'*': [.9, {var: 'width'}]}}, {floor: {'*': [.35, {var: 'height'}]}}],
        font: 'Toyota-Type-Book',
        fontsize: {'/': [{sqrt: {'*': [{var: 'width'}, {var: 'height'}]}}, 60]},
        position: ['center', 'bottom'],
        align: 'west',
        opacity: 1,
      }}
    },}
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