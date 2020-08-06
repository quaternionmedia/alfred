import m from 'mithril'
var state = require("./Globals").state

export function Head() {
  return {
    view: vnode => {
      return m('#head.head', {
        style: {
          width: window.innerWidth > window.innerHeight ? `${state.width()/state.height()*40}vh` : `${state.width()/state.height()*24}vh`,
          height: window.innerWidth > window.innerHeight ? '40vh' : '24vh'
        },
        ...vnode.attrs
      }, vnode.children)
    }
  }
}
