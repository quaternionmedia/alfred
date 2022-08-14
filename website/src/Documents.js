import m from 'mithril'
import './styles/documents.scss'

export const Documents = {
  view: vnode => [
    m('h1', 'Documents'),
    m('a.docLink', { href: '/docs/' }, 'User Documentation'),
    m('a.docLink', { href: '/api' }, 'API Reference'),
  ],
}
