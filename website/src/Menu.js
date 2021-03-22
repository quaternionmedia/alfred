import m from 'mithril'
import './menu.css'
import { User } from './User'
import { message } from 'alertifyjs'

function Menu() {
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
        m(Links),
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
          m(Link, {href:'/', id: 'home-link'}, 'home'),
          m(Link, {href: '/form', id: 'form-link'}, 'form'),
          m(Link, {href:'/projects', id: 'projects-link'}, 'projects'),
          m(Link, {href: '/renders', id: 'renders-link'}, 'renders'),
          m(Link, {
            href:'/login',
            id: 'login-link',
            onclick: vnode => {
              if (User.username) {
                message(`${User.username} logged out`)
                User.logout()
              }
            }
          }, User.username ? 'logout' : 'login'),
          m(Link, {href:'/magnussens', id: 'magnussens-link'}, 'Magnussens'),
        ]}}}
export { Menu, Links, Link }
