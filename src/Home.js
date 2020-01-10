import m from 'mithril'
import { Menu, Links } from './Menu'

const Home = () => {
  return {
    view: (vnode) => {
      return [
        m(Menu),
        m('span#main', {}, [
          m('h3.title', {align: 'center'}, 'Alfred. The serverless video editor'),
        ]),
        Links,
      ]
    }
  }
}

export default Home
