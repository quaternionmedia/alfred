import m, { render } from 'mithril'
import { message } from 'alertifyjs'
import { User } from './User'
import LOGO from './assets/alWhite.png'
import './styles/menu.scss'

export function Menu() {
  // toggles the navContainer visibility
  var open = false
  addEventListener('resize', () => {
    if (window.innerWidth >= 1026 && open) {
      open = false
      m.redraw()
    }
  })
  function toggle() {
    console.log('toggling menu', open)
    open = !open
  }

  return {
    view: vnode => {
      return [
        m(
          'header',
          m('.navbutton', m('i.material-icons', { onclick: toggle }, 'menu')),
          m('.navContainer', { style: { width: open ? '250px' : '0px' } }, [
            m(navLinks, { onclick: toggle }),
          ]),
          //TODO: change logo to new image in the future when location of images is known
          m(
            'div.logo',
            m(
              Link,
              { href: '/', id: 'home-link', ...vnode.attrs },
              m('img.logoImg', { src: LOGO })
            )
          ),
          m('.menuLinks', m(Links)),
          m(
            Link,
            {
              class: 'loginLink',
              href: User.username ? '/logout' : '/login',
              id: 'login-link',
              ...vnode.attrs,
            },
            User.username ? 'Logout' : 'Login'
          )
        ),
      ]
    },
  }
}

//an individual link
export const Link = () => ({
  view: vnode => {
    return m(
      m.route.Link,
      {
        class: window.location.hash.startsWith(vnode.attrs.href, 2)
          ? 'active'
          : '',
        ...vnode.attrs,
      },
      vnode.children
    )
  },
})

//the links in the menu bar
export const Links = () => ({
  view: vnode => [
    m(
      Link,
      {
        href: '/projects',
        id: 'projects-link',
        ...vnode.attrs,
      },
      'PROJECTS'
    ),
    m(
      Link,
      {
        href: '/renders',
        id: 'renders-link',
        ...vnode.attrs,
      },
      'RENDERS'
    ),
  ],
})

//the links in the nav bar, separated to have own style
export const navLinks = () => ({
  view: vnode => [
    m(
      Link,
      { class: 'navLink', href: '/', id: 'home-link', ...vnode.attrs },
      'HOME'
    ),
    m(
      Link,
      {
        class: 'navLink',
        href: '/projects',
        id: 'projects-link',
        ...vnode.attrs,
      },
      'PROJECTS'
    ),
    m(
      Link,
      {
        class: 'navLink',
        href: '/renders',
        id: 'renders-link',
        ...vnode.attrs,
      },
      'RENDERS'
    ),
    m(
      Link,
      {
        class: 'navLink',
        href: User.username ? '/logout' : '/login',
        id: 'login-link',
        ...vnode.attrs,
      },
      User.username ? 'LOGOUT' : 'LOGIN'
    ),
  ],
})
