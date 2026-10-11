import m from 'mithril'
import './styles/footer.scss'
import { User } from './User'
import { Link } from './Menu'

export const Footer = {
  view: vnode =>
    m('footer', {}, [
      // The documentation links, which used to be a route of their own at
      // #!/documents -- a whole view, outside the editor, for two links. They
      // are always to hand here and cost nobody a navigation.
      m('a.docLink', { href: '/docs/' }, 'User documentation'),
      m('a.docLink', { href: '/api' }, 'API reference'),
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
      m('.text', 'More information at '),
      m(
        'a.link',
        { href: 'https://www.quaternion.media/alfred/' },
        'quaternion.media/alfred'
      ),
    ]),
}
