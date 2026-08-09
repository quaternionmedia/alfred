import m, { render } from 'mithril'
import { message } from 'alertifyjs'
import { User } from './User'
// `import LOGO from './assets/alWhite.png'` yielded an object here, not a URL,
// so the logo rendered as src="[object Object]" on every page and the browser
// fetched /[object%20Object] -- eleven 404s per session in the API log. This is
// the idiom Parcel 2 documents for ESM, and it resolves to a string.
const LOGO = new URL('./assets/alWhite.png', import.meta.url).href
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
    open = !open
  }

  // Closing on navigation matters on a phone: the drawer covers the editor,
  // and leaving it open after a tap hides the thing you just navigated to.
  function close() {
    open = false
  }

  return {
    view: vnode => {
      // One set of links, rendered once.
      //
      // This rendered `navLinks` into a drawer *and* `Links` into the bar, both
      // carrying the same destinations with the same element ids -- so every id
      // in the header appeared twice, and `navigation.spec.js` pinned that as a
      // known defect. Two copies also meant two things to keep in step, which
      // they were not: the drawer carried HOME and LOGIN and the bar did not.
      //
      // Whether the list is a drawer or a row is now a question for CSS, which
      // is where it belongs. The stage rail carries navigation *within* the
      // editor, so this header only has to get you between the few views that
      // are not the editor.
      return m('header', { class: open ? 'open' : '' }, [
        m(
          '.navbutton',
          m('i.material-icons', { onclick: toggle, title: 'menu' }, 'menu')
        ),
        m(
          'div.logo',
          m(
            Link,
            { href: '/', id: 'home-link', ...vnode.attrs },
            m('img.logoImg', { src: LOGO })
          )
        ),
        m('nav.menuLinks', m(Links, { onclick: close })),
        m(
          Link,
          {
            class: 'loginLink',
            href: User.username ? '/logout' : '/login',
            id: 'login-link',
            onclick: close,
            ...vnode.attrs,
          },
          User.username ? 'Logout' : 'Login'
        ),
      ])
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
        // Into the flow, not to the retired standalone views. Those routes
        // still redirect here, so an old bookmark works; the menu should not
        // teach the old path.
        href: '/?stage=source',
        id: 'projects-link',
        ...vnode.attrs,
      },
      'PROJECTS'
    ),
    m(
      Link,
      {
        href: '/?stage=deliver',
        id: 'renders-link',
        ...vnode.attrs,
      },
      'RENDERS'
    ),
    m(
      Link,
      {
        href: '/documents',
        id: 'documents-link',
        ...vnode.attrs,
      },
      'DOCUMENTS'
    ),
  ],
})

