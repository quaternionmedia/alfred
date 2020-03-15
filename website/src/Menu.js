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
        Links,
        ]),
        m('i.material-icons', {onclick: toggle, style: {display: open ? 'none' : '' }}, 'menu'),
      ]
    }
  }
}
const Link = () => {
  return {
    view: (vnode) => {
      return m('.menu-item', [
        m(m.route.Link, vnode.attrs, vnode.children)
      ])
    }
  }
}

const Links = [
  m(Link, {href:'/'}, 'home'),
  m(Link, {href:'/projects'}, 'projects'),
  m(Link, {href: '/renders'}, 'renders'),
  m(Link, {href:'/login'}, 'login'),
]
export { Menu, Links, Link }
