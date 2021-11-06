import m from 'mithril'
import './menu.css'
import { User } from './User'
import { message } from 'alertifyjs'

function Menu() {
  var open = false
  function toggle() {
    console.log('toggling menu', open)
    open = !open
  }
  return {
    view: (vnode) => {
      return [
        m('#menu.menu', {style: {display: open ? '': 'none', width: open ? '250px' : '0px'}}, [
          m('i.material-icons', {onclick: toggle}, 'close'),
        m(Links, {onclick: toggle}),
        ]),
        m('img.logo', {src: '/al-white.svg', onclick: toggle, style: {display: open ? 'none' : '' }}),
      ]
    }
  }
}
function Link() {
  return {
    view: (vnode) => {
      return m('.menu-item', [
        m(m.route.Link, vnode.attrs, vnode.children)
      ])
    }
  }
}

function Links() {
  return {
    view: vnode => {
      return [
        m(Link, {href:'/', id: 'home-link', ...vnode.attrs}, 'home'),
        m(Link, {href:'/projects', id: 'projects-link', ...vnode.attrs}, 'projects'),
        m(Link, {href: '/renders', id: 'renders-link', ...vnode.attrs}, 'renders'),
        m(Link, {
          href: User.username ? '/logout' : '/login',
          id: 'login-link',
          ...vnode.attrs
        }, User.username ? 'logout' : 'login'),
      ]
    }
  }
}


export { Menu, Links, Link }
