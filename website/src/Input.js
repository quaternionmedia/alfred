import m from 'mithril'
import { ContentEditable } from 'mithril-contenteditable'
var Stream = require("mithril/stream")

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
  media: Stream(['']),
  audio: Stream(['']),
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
