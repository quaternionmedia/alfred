import m from 'mithril'
import { ContentEditable } from 'mithril-contenteditable'
var Stream = require("mithril/stream")
import { Sortable, MultiDrag } from 'sortablejs'
Sortable.mount(new MultiDrag());
import { array_move } from './Video'
import { message, success, error } from 'alertifyjs'

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
  media: Stream([]),
  audio: Stream([]),
  call: Stream(''),
  closing: Stream(''),
  fontcolor: Stream('#FFFFFF'),
  themecolor: Stream('#CC5500'),
  font: Stream('Segoe_UI_Bold'),
  duration: Stream(5),
  clear: () => {
    console.log('clearing form')
    VideoForm.project = Stream('')
    VideoForm.name = Stream('')
    VideoForm.logo = Stream('')
    VideoForm.address = Stream('')
    VideoForm.phone = Stream('')
    VideoForm.hours = Stream('')
    VideoForm.website = Stream('')
    VideoForm.initial = Stream('')
    VideoForm.bullets = Stream('')
    VideoForm.media = Stream([])
    VideoForm.audio = Stream([])
    VideoForm.call = Stream('')
    VideoForm.closing = Stream('')
    VideoForm.fontcolor = Stream('#FFFFFF')
    VideoForm.themecolor = Stream('#CC5500')
    VideoForm.font = Stream('Segoe_UI_Bold')
    VideoForm.duration = Stream(5)
  }
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
        m('input', {
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
        // multiDrag: true,
        group: 'media',
        selectedClass: "selected",
        swapThreshold: 0.50,
        animation: 150,
        ghostClass: 'ghost',
        forceFallback: true,
        // delay: 100,
        preventOnFilter: false,
        onUpdate: e => {
          let media
          if (e.oldIndicies.length > 0) {
            media = VideoForm.media()
            let indicies = []
            e.oldIndicies.forEach((item, i) => {
              indicies.push(item.index)
            })
          indicies.sort(function(a,b){ return b - a; })
          // console.log('moving multiple', indicies)
          let moved = []
          indicies.forEach((item, i) => {
            moved.unshift(...media.splice(item, 1))
          })
          // console.log('unshifted', moved)
          media.splice(e.newIndicies[0], 0, ...moved)
          } else {
          media = array_move(VideoForm.media(), e.oldIndex, e.newIndex)
        }
          VideoForm.media([''])
          m.redraw.sync()
          VideoForm.media(media)
          m.redraw()
          // console.log('moved media', e, media)
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
        let media = VideoForm.media()
        let n = media.length
        for (var i = 0; i < files.length; i++ ) {
          // let medium = (URL.createObjectURL(f))
          let filename = files[i].name
          console.log('adding', files[i])
          form.append('file', files[i])
          message(`uploading file ${filename}`, 3)
          media.push(filename)
          m.request('/upload', {
            method: 'POST',
            body: form,
            config: xhr => {
              xhr.upload.addEventListener('progress', e => {
                let el = document.getElementById(`${filename}`)
                let v = 100 * e.loaded / e.total
                  m.render(el, m('progress', { id: `${filename}-progress`, max: 100, value: v }))
                console.log('upload progress', e, el, v)
                el.value = v
              })
            }
          })
          .then(data => {
            let tmp = VideoForm.media()
            tmp.splice(tmp.indexOf(filename), 1, data.filename)
            VideoForm.media(tmp)
            console.log('upload successfully!', data.filename, VideoForm.media(), files[i])
            success(`successfully uploaded ${data.filename}`, 5)
            let el = document.getElementById(`${filename}`)
            m.render(el, m('video[controls].formthumb', {src: data.filename}))

          })
          .catch(error => {
            console.error(error)
            error(`error uploading file ${filename}`)
          })
        }
        VideoForm.media(media)
        m.redraw()
      }})
    },
    onchange: (vnode) => {
      console.log('element changed', vnode)
    },
    view: (vnode) => {
      return m('', {}, [
        VideoForm.media().map(medium => {
          if (medium && medium.endsWith('.mp4')) {
            return m(`.medium`, { id: medium }, m('video[controls].formthumb.media', { src: medium }))
          } else {
            return m('img.formthumb.media', { src: medium, id: medium })
        }
        }),
      ]
      )
    }
  }
}

export function NewMedia() {
  return {
    view: vnode => {
      return m('.bar', {}, [
        m('input', {id: 'newMedia'}),
        m('input[type=submit].button', {
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
      ])
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
        m('audio[controls].audiothumb', {
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
