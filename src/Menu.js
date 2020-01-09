import m from 'mithril'
import './menu.css'

const Menu = () => {
  var open = false
  function toggle() {
    console.log('toggling', open)
    open = !open
  }
  return {
    view: (vnode) => {
      return [
        m('#menu.menu', {style: {display: open ? '': 'none', width: open ? '250px' : '0px'}}, [
          m('i.material-icons', {onclick: toggle}, 'close'),
          m('.menu-item', 'item1'),
        ]),
        m('i.material-icons', {onclick: toggle, style: {display: open ? 'none' : '' }}, 'menu'),
      ]
    }
  }
}

export default Menu
