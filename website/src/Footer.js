import m from 'mithril'
import './styles/footer.scss'

export const Footer = {
  view: vnode =>
    m('footer', {}, [
      m('.text', 'More information at '),
      m(
        'a.link',
        { href: 'https://www.quaternion.media/alfred/' },
        'quaternion.media/alfred'
      ),
    ]),
}
