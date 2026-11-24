import m from 'mithril'
// `import LOGO from './assets/alWhite.png'` yielded an object here, not a URL,
// so the logo rendered as src="[object Object]" on every page and the browser
// fetched /[object%20Object] -- eleven 404s per session in the API log. This is
// the idiom Parcel 2 documents for ESM, and it resolves to a string.
const LOGO = new URL('./assets/alWhite.png', import.meta.url).href
import './styles/menu.scss'

export const Menu = {
  view: vnode =>
    // One set of links, rendered once.
    //
    // This rendered `navLinks` into a drawer *and* `Links` into the bar, both
    // carrying the same destinations with the same element ids -- so every id
    // in the header appeared twice, and `navigation.spec.js` pinned that as a
    // known defect. The stage rail carries navigation within the editor, so
    // this header only has to get you between the few views that are not the
    // editor.
    //
    // No menu button. Below 1026 pixels it opened the links as a drawer over
    // the editor, and once the links had all gone to the rail it opened an
    // empty one: the only control in the header of a phone, and it did
    // nothing. A link that belongs here later sits in the row.
    m('header', [
      m(
        'div.logo',
        m(
          Link,
          { href: '/', id: 'home-link', ...vnode.attrs },
          m('img.logoImg', { src: LOGO, alt: 'Alfred' })
        )
      ),
      m('nav.menuLinks', m(Links)),
    ]),
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

// The links in the menu bar.
//
// Empty, and deliberately so. It carried PROJECTS and RENDERS, which pointed
// at `?stage=source` and `?stage=deliver` -- two of the four stages the rail
// already lists, directly below, with the other two beside them. A second
// control for the same destination is not redundancy, it is a second thing to
// keep in step and a second place to look.
//
// The component stays because the header still needs somewhere to put a link
// that belongs to the whole app rather than to the editor. There is no such
// link today.
export const Links = () => ({
  view: () => [],
})
