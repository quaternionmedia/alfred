import m from 'mithril'
import { Menu, Links } from './Menu'

function Home() {
  return {
    view: (vnode) => {
      return [
        m(Menu),
        m('span#main', {}, [
          m('h3.title', {align: 'center'}, 'Alfred. The serverless video editor'),
        ]),
        m(Links),
      ]
    }
  }
}

export default Home
