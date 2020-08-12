import m from 'mithril'
var state = require("./Globals").state

export function Head() {
  return {
    oncreate: vnode => {
      window.onresize = e => {
        let h = state.width()/state.height()*window.innerHeight
        // console.log('updating head', h, e)
        vnode.dom.style.width = window.innerWidth > window.innerHeight ? `${h*.4}` : `${h*.24}`
        vnode.dom.style.height = window.innerWidth > window.innerHeight ? '40vh' : '24vh'
      }
    },
    view: vnode => {
      return m('#head.head', {
        style: {
          width: window.innerWidth > window.innerHeight ? `${state.width()/state.height()*window.innerHeight*.4}` : `${state.width()/state.height()*window.innerHeight*.24}`,
          height: window.innerWidth > window.innerHeight ? '40vh' : '24vh'
        },
        ...vnode.attrs
      }, vnode.children)
    }
  }
}
