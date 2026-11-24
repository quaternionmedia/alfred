import m from 'mithril'
let components = require('./Components')

/** A project's `fields`, each drawn by the component its `type` names. */
export function Fields() {
  return {
    view: vnode => {
      return vnode.children.map(field => {
        return m(components[field.type], field.attrs, field.children)
      })
    }
  }
}
