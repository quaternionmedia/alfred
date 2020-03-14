import m from 'mithril'


const Bin = () => {
  var media = []
  return {
    oninit: (vnode) => {
      m.request('/videos').then( e => {
        console.log('got videos!', e)
        media = e
      })
    },
    view: (vnode) => {
      return m('#bin.project.bin', {}, [
        m('h3', 'bin'),
        m('table', {}, [
          m('tr', [
            m('th', 'files'),
          ]),
          media.map(f => {
            return m('tr', [
              m('td', {
              }, f)
            ])
          })
        ])
      ])
    }
  }
}

export default Bin
