import m from 'mithril'
import Bin from './Bin'

export function Import() {
  function importFiles(e) {
    console.log('imported files', e)
    Array.from(e.target.files).forEach(i => Bin.media.push(URL.createObjectURL(i)))
    m.redraw()
    // console.log('new media list', media)
  }
  return {
    oninit: vnode => {
      if (window.File && window.FileReader && window.FileList && window.Blob) {} else {
        alert('The File APIs are not fully supported in this browser.');
      }
    },
    view: vnode => {
      return m('input#files', {
          multiple: true,
          name: 'files[]',
          type: 'file',
          oncreate: vnode => {
            vnode.dom.addEventListener('change', importFiles, false)
          },
        })
    }
  }
}
