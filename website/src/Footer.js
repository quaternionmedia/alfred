import m from 'mithril'
import './styles/footer.scss'
import { User } from './User'
import { Link } from './Menu'

/** A visible, readable break between two links that sit on one line. */
const separator = () => m('span.sep', { 'aria-hidden': 'true' }, ' · ')

export const Footer = {
  view: vnode =>
    m('footer', {}, [
      // The documentation links, which used to be a route of their own at
      // #!/documents -- a whole view, outside the editor, for two links. They
      // are always to hand here and cost nobody a navigation.
      //
      // Separated. They were two bare anchors side by side with nothing
      // between them -- the stylesheet that spaced them is not loaded here --
      // so the footer read "User documentationAPI reference", one link to the
      // eye and one run-on phrase to anything reading the text.
      m('nav.doclinks', { 'aria-label': 'Documentation' }, [
        m('a.docLink', { href: '/docs/' }, 'User documentation'),
        separator(),
        m('a.docLink', { href: '/api' }, 'API reference'),
      ]),
      separator(),
      // Ending a session is a rare, deliberate act, and it sat in the header
      // beside the navigation as though it were a destination. Here it is
      // still one click and no longer competes with the work.
      m(
        Link,
        {
          class: 'loginLink sessionLink',
          href: User.username ? '/logout' : '/login',
          id: 'login-link',
        },
        User.username ? 'Logout' : 'Login'
      ),
      separator(),
      m('.text', 'More information at '),
      m(
        'a.link',
        { href: 'https://www.quaternion.media/alfred/' },
        'quaternion.media/alfred'
      ),
    ]),
}
