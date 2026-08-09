import m from 'mithril'
import './styles/footer.scss'

export const Footer = {
  view: vnode =>
    m('footer', {}, [
      // The documentation links, which used to be a route of their own at
      // #!/documents -- a whole view, outside the editor, for two links. They
      // are always to hand here and cost nobody a navigation.
      m('a.docLink', { href: '/docs/' }, 'User documentation'),
      m('a.docLink', { href: '/api' }, 'API reference'),
      m('.text', 'More information at '),
      m(
        'a.link',
        { href: 'https://www.quaternion.media/alfred/' },
        'quaternion.media/alfred'
      ),
    ]),
}
