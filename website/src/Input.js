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
      return m('', {}, [
        m('label', { for: vnode.attrs.name }, vnode.children),
        m('input[type=text]', {
        oninput: e => {
          console.log('input ', vnode.dom.value, e.target.value)
          VideoForm[vnode.attrs.name](e.target.value)
        },
        value: VideoForm[vnode.attrs.name](),
        ...vnode.attrs,
      }),
      m('p.textthumb', vnode.attrs, VideoForm[vnode.attrs.name]())
    ])
    }
  }
}


export function InputArea() {
  return {
    view: (vnode) => {
      return m('', {}, [
        m('label', { for: vnode.attrs.name }, vnode.children),
        m('textarea', {
        oninput: e => {
          console.log('input ', vnode.dom.value, e.target.value)
          VideoForm[vnode.attrs.name](e.target.value)
        },
        value: VideoForm[vnode.attrs.name](),
        ...vnode.attrs,
      }),
      m('p.textthumb', vnode.attrs, VideoForm[vnode.attrs.name]())
    ])
    }
  }
}


export function Image() {
  return {
    view: (vnode) => {
      return m('.bar', {}, [
        m('label', { for: vnode.attrs.name }, vnode.children),
        m('textarea', {
        oninput: e => {
          console.log('input ', vnode.dom.value, e.target.value)
          VideoForm[vnode.attrs.name](e.target.value)
        },
        value: VideoForm[vnode.attrs.name](),
        ...vnode.attrs,
      }),
      m('img.formthumb', {
        src: VideoForm[vnode.attrs.name](),
      }),
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
          let media = array_move(VideoForm.media(), e.oldIndex, e.newIndex)
          VideoForm.media([''])
          m.redraw.sync()
          VideoForm.media(media)
          m.redraw()
          console.log('moved media', e, media)
        },
        removeOnSpill: true,
        onSpill: e => {
          var media = VideoForm.media()
          if (e.oldIndicies.length > 0) {
            let indicies = []
            e.oldIndicies.forEach((item, i) => {
              indicies.push(item.index)
            })
          indicies.sort(function(a,b){ return b - a; })
          indicies.forEach((item, i) => {
            console.log('removing', item)
            media.splice(item, 1)
          })
          } else {
            media.splice(e.oldIndex, 1)
          }
          VideoForm.media(media)
          console.log('spilling', e, VideoForm.media())
        },
      })

      // setup drag and drop file upload
      dragdrop(vnode.dom, {onchange: files => {
        console.log('dropped', files, files.length)
        let form = new FormData()
        for (var i = 0; i < files.length; i++ ){
          // let medium = (URL.createObjectURL(f))
          console.log('adding', files[i])
          form.append('file', files[i])
          fetch('/upload', {
            method: 'POST',
            body: form
          })
          .then(response => response.json())
          .then(data => {
            let media = VideoForm.media()
            media.push(data.filename)
            VideoForm.media(media)
            console.log('upload successfully!', data.filename, VideoForm.media())
            m.redraw()

          })
          .catch(error => {
            console.error(error)
          })
        }
      }})
    },
    onchange: (vnode) => {
      console.log('element changed', vnode)
    },
    view: (vnode) => {
      return m('', {}, [
        VideoForm.media().map(medium => {
          if (medium && medium.endsWith('.mp4')) {
            return m('.media.bar', [
              m('textarea', { value: medium , name: `${vnode.attrs.name}[]`}),
              m('video[controls].formthumb', { src: medium }),
            ])
          } else {
          return m('.media.bar', [
            m('textarea', { value: medium , name: `${vnode.attrs.name}[]`}),
            m('img.formthumb', { src: medium }),
          ])}
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
              m.request(newMedia.value, {
                type: 'head',
                extract: (xhr, options) => {
                  console.log('extracting', xhr)
                  xhr.onreadystatechange = () => {
                    if (xhr.readystate == 4) {
                      console.log(xhr.status);
                      console.log('type', xhr.getResponseHeader("Content-Type"));
                    }
                  }
                  // return options.deserialize()
                },
              }).then(res => {
                console.log('newMedia head', res)

              })
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
      return m('', {}, [
        m('label', { for: vnode.attrs.name }, vnode.children),
        m('input[type=color]', {
        oninput: e => {
          VideoForm[vnode.attrs.name](e.target.value)
          console.log('input ',e.target.value, VideoForm[vnode.attrs.name]())
          m.redraw()
        },
        value: VideoForm[vnode.attrs.name](),
        ...vnode.attrs,
      }),
      m('.textthumb', {style: {background: VideoForm[vnode.attrs.name]()}})
    ])
    }
  }
}

export function Audio() {
  return {
    view: (vnode) => {
      return m('', {}, [
        m('label', { for: vnode.attrs.name }, vnode.children),
        m('textarea', {
        oninput: e => {
          console.log('input ', vnode.dom.value, e.target.value)
          VideoForm[vnode.attrs.name](e.target.value)
        },
        value: VideoForm[vnode.attrs.name](),
        ...vnode.attrs,
        }),
        m('audio[controls]', {
            src: VideoForm[vnode.attrs.name](),
            type: 'audio/mpeg',
        }),
      ])
    }
  }
}

export function dragdrop(element, options) {
    options = options || {}

    element.addEventListener("dragover", activate)
    element.addEventListener("dragleave", deactivate)
    element.addEventListener("dragend", deactivate)
    element.addEventListener("drop", deactivate)
    element.addEventListener("drop", update)

    function activate(e) {
        e.preventDefault()
    }
    function deactivate() {}
    function update(e) {
        e.preventDefault()
        if (typeof options.onchange == "function") {
            options.onchange((e.dataTransfer || e.target).files)
        }
    }
}
