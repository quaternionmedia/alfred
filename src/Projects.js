import m from 'mithril'
import { Menu, Links } from './Menu'

const Projects = () => {
  return {
    view: (vnode) => {
      return m('.projects', [
        m(Menu),
        Links,
        m('p', 'projects:'),
      ])
    }
  }
}

export default Projects
