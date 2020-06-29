import m from 'mithril'
import { success, error } from 'alertifyjs'
import { Menu } from './Menu'


export function Form() {

  var options = []
  var selected = {}

  function Dropdown() {
    return {
      view: (vnode) => {
        return m('select', {
          onchange: e => {
            let i = e.target.selectedIndex
            console.log('form res', options, i)
            if (options && i) {
              m.request(`/project/${options[i - 1]}`).then(res => {
                selected = res['form']
                console.log('selected', selected)
                // selected['name'] = options[i - 1]
              })
            }
          }
        }, [
          m('option', {value: '', ...vnode.attrs}, ''),
          vnode.children.map( opt => {
            return m('option', {
            value: opt
          }, opt)})
        ])
      }
    }
  }

  function Text() {
    return {
      view: (vnode) => {
        return m('', {}, [
          m('label.formlabel', {
            for: vnode.attrs.name
          }, vnode.children),
          m('input', {
            ...vnode.attrs,
            value: selected ? selected[vnode.attrs.name] : ''
          })
        ])
      }
    }
  }
  function TextArea() {
    return {
      view: (vnode) => {
        return m('', {}, [
          m('label.formlabel', {
            for: vnode.attrs.name
          }, vnode.children),
          m('textarea', {
            ...vnode.attrs,
            value: selected ? selected[vnode.attrs.name] : ''
          })
        ])
      }
    }
  }
  function Color() {
    return {
      view: (vnode) => {
        return m('', {}, [
          m('label.formlabel', {
            for: vnode.attrs.name
          }, vnode.children),
          m('input', {
            type: 'color',
            ...vnode.attrs,
            value: selected ? selected[vnode.attrs.name] : ''
          })
        ])
      }
    }
  }

  return {
    oninit: (vnode) => {
      m.request('/projects').then(e => {
        options = e
        console.log('projects', options)
      })
    },

    view: (vnode) => {
      return m('form.form#form', {

      }, [
        m(Dropdown, options),
        m('br'),
        m(Text, {name: 'project', id:'projectName'}, 'Project Name'),
        m('', {style: {'text-align': 'right'}}, [
          m('input', {type: 'submit', name: 'save', value: 'save',
            onclick: e => {
              e.preventDefault()
              let form = new FormData(document.getElementById('form'))
              console.log('saving form', e, form)
              let proj = document.getElementById('projectName').value
              m.request('/save', {
                method: 'post',
                params: {
                  project: proj
                },
                body: form
              })
            },
          },),
        ]),
        m('hr'),
        m(Text, {name: 'NAME'}, 'Business Name'),
        m(Text, {name: 'LOGO'}, 'Logo'),
        m(TextArea, {name: 'ADDRESS'}, 'Address'),
        m(Text, {name: 'PHONE'}, 'Phone'),
        m(Text, {name: 'HOURS'}, 'Hours'),
        m(Text, {name: 'WEBSITE'}, 'Website'),
        m(TextArea, {name: 'INITIAL'}, 'Initial text'),
        m(TextArea, {name: 'BULLETS'}, 'Bullets'),
        m(TextArea, {name: 'OPTIONAL'}, 'Optional'),
        m(TextArea, {name: 'MEDIA'}, 'Media'),
        m(TextArea, {name: 'AUDIO'}, 'Audio'),
        m(TextArea, {name: 'CALL'}, 'Call'),
        // m(TextArea, {name: 'CLOSING'}, 'Closing'),
        m(Color, {name: 'THEMECOLOR', value:'#FF0'}, 'Theme Color'),
        m(Color, {name: 'FONTCOLOR', value: '#FFF'}, 'Font Clolor'),
        m(Text, {name: 'FONT'}, 'Font'),
        m(Text, {name: 'DURATION'}, 'Duration'),
        m('hr'),
        m('', {style: {'text-align': 'right'}}, [
          m('input', {type: 'submit', name: 'render', value: 'render',
            onclick: (e) => {
              e.preventDefault()
              let form = new FormData(document.getElementById('form'))
              let proj = document.getElementById('projectName').value
              console.log('rendering from form', e, form)
              m.request('/form', {
                method: 'post',
                params: {
                  project: proj
                },
                body: form,
              }).then(e => {
                console.log('rendering', e)
                success(`rendering!`)
                m.route.set('/renders')
              }, e => {
                console.log('error rendering', e)
                error('oops... something went wrong.')
              })
            }
          }, )
        ]),
      ])
    }
  }
}

export function FormPage() {
  return {
    view: (vnode) => {
      return [
        m(Menu),
        m(Form)
    ]
    }
  }
}
