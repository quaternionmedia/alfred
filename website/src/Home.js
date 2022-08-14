import m from 'mithril'

export const Home = {
  view: vnode => [
    m('span#main', {}, [
      m('h3.title', { align: 'center' }, 'Alfred: the automatic video editor'),
    ]),
    m('br'),
    m('a', { href: '/docs/' }, 'User Documentation'),
    m('br'),
    m('a', { href: '/api' }, 'API Reference'),
    m('br'),
    m('br'),
    'More information at ',
    m(
      'a',
      { href: 'https://quaternion.media/alfred' },
      'quaternion.media/alfred'
    ),
  ],
}
