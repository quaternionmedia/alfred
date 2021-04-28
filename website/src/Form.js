import m from 'mithril'
import { success, error, message } from 'alertifyjs'
let components = require('./Components')

export function Fields() {
  return {
    view: vnode => {
      return vnode.children.map(field => {
        return m(components[field.type], field.attrs, field.children)
      })
    }
  }
}

export const MagnussensFields = [
  // { type: 'Selector', attrs: { name: 'project', text: 'Video', }, children: [ 'Magnussens', 'RSG']) },
  { type: 'Selector', attrs: { name: 'duration', text: 'Duration',}, children: ['30', '15'] },
  { type: 'TextBox', attrs: { name: 'carname', text: 'Car Name' } },
  { type: 'TextBox', attrs: { name: 'offerinfo', text: 'Offer Info' } },
  { type: 'Selector', attrs: { name: 'offeralign', text: 'Offer alignment' }, children: ['left', 'center'] },
  { type: 'TextBox', attrs: { name: 'legaltext', text: 'Legal Text' } },
]