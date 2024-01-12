import m from 'mithril'
import './styles/documents.scss'

export const Documents = {
  view: vnode => [
    m('h1', 'Documents'),
    m(
      'a.docLink',
      { href: 'https://quaternionmedia.github.io/alfred/' },
      'User Documentation'
    ),
    m('a.docLink', { href: '/api' }, 'API Reference'),
  ],
}
