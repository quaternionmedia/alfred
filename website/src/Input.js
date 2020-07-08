import m from 'mithril'
import { ContentEditable } from 'mithril-contenteditable'
var Stream = require("mithril/stream")
import { Sortable, MultiDrag } from 'sortablejs'
Sortable.mount(new MultiDrag());
import { array_move } from './Video'

export var VideoForm = {
  project: Stream(''),
  name: Stream(''),
  logo: Stream(''), //AnyUrl
  address: Stream(''),
  phone: Stream(''),
  hours: Stream(''),
  website: Stream(''), //AnyUrl = 'talahairstudio.com'
  initial: Stream(''),
  bullets: Stream(''),
  optional: Stream(''),
  media: Stream([]),
  audio: Stream([]),
  call: Stream(''),
  closing: Stream(''),
  fontcolor: Stream('#FFFFFF'),
  themecolor: Stream('#CC5500'),
  font: Stream('Segoe_UI_Bold'),
  duration: Stream(5),
}


export function Field() {
  return {
    view: (vnode) => {
      return [
        m('label', { for: vnode.attrs.name }, vnode.children),
        m(ContentEditable, {
          // html: VideoForm[vnode.attrs.name],
          html: this.html,
          oncreate: html => {
            this.html = VideoForm[vnode.attrs.name]()
          },
          onchange: html => {
            this.html = html
            VideoForm[vnode.attrs.name](html)
            console.log('field changed', html)
          },
          onChanged: v => {
            VideoForm[vnode.attrs.name](v)
          },
          onkeydown: e => {
            switch (e.key) {
              case 'Enter':
                e.preventDefault()
                // console.log('enter', VideoForm.name(), VideoForm[vnode.attrs.name]())
            }
          },
          ...vnode.attrs,
      })
    ]
    }
  }
}

export function Input() {
  return {
    view: (vnode) => {
      return [
        m('label', { for: vnode.attrs.name }, vnode.children),
        m('input[type=text]', {
        oninput: e => {
          console.log('input ', vnode.dom.value, e.target.value)
          VideoForm[vnode.attrs.name](e.target.value)
        },
        value: VideoForm[vnode.attrs.name](),
        ...vnode.attrs,
      })
    ]
    }
  }
}


export function InputArea() {
  return {
    view: (vnode) => {
      return [
        m('label', { for: vnode.attrs.name }, vnode.children),
        m('textarea', {
        oninput: e => {
          console.log('input ', vnode.dom.value, e.target.value)
          VideoForm[vnode.attrs.name](e.target.value)
        },
        value: VideoForm[vnode.attrs.name](),
        ...vnode.attrs,
      })
    ]
    }
  }
}


export function Image() {
  return {
    view: (vnode) => {
      return m('.bar', {}, [
        m('label', { for: vnode.attrs.name }, vnode.children),
        m('input', {
        oninput: e => {
          console.log('input ', vnode.dom.value, e.target.value)
          VideoForm[vnode.attrs.name](e.target.value)
        },
        value: VideoForm[vnode.attrs.name](),
        ...vnode.attrs,
      }),
      m('img.formthumb', {
        src: VideoForm[vnode.attrs.name](),
        style: {
          width: '30%',
          padding: '1em'
        }
      })
    ])
    }
  }
}

export function Media() {
  return {
    oncreate: (vnode) => {
      new Sortable(vnode.dom, {
        multiDrag: true,
        // group: 'media',
        selectedClass: "selected",
        swapThreshold: 0.50,
        animation: 150,
        ghostClass: 'ghost',
        forceFallback: true,
        // delay: 100,
        invertSwap: true,
        preventOnFilter: false,
        onUpdate: e => {
          let form = array_move(VideoForm.media(), e.oldIndex, e.newIndex)
          VideoForm.media([''])
          m.redraw.sync()
          VideoForm.media(form)
          m.redraw()
          console.log('moved media', e, form)
        },
        removeOnSpill: true,
        onSpill: e => {
          VideoForm.media(VideoForm.media().splice(e.oldIndex, 1))
          console.log('spilling', e, VideoForm.media())
        },
      })
    },
    view: (vnode) => {
      return m('', {}, [
        VideoForm.media().map(medium => {
          return m('.media.bar', [
            m('input', { value: medium , name: `${vnode.attrs.name}[]`}),
            m('img.formthumb', { src: medium }),
          ])
        }),
        m('.bar', {}, [
          m('input', {id: 'newMedia'}),
          m('input[type=submit]', {
            value: 'add new media',
            onclick: e => {
              e.preventDefault()
              console.log('adding new media', e)
              let form = VideoForm.media()
              let newMedia = document.getElementById('newMedia')
              if (newMedia.value) {
                form.push(newMedia.value)
                VideoForm.media(form)
              }
            }
          }, )
        ]),
      ]
      )
    }
  }
}

export function Color() {
  return {
    view: (vnode) => {
      return [
        m('label', { for: vnode.attrs.name }, vnode.children),
        m('input[type=color]', {
        oninput: e => {
          VideoForm[vnode.attrs.name](e.target.value)
          console.log('input ',e.target.value, VideoForm[vnode.attrs.name]())
          m.redraw()
        },
        value: VideoForm[vnode.attrs.name](),
        ...vnode.attrs,
      })
    ]
    }
  }
}
