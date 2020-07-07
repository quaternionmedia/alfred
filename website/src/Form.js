import m from 'mithril'
import { success, error } from 'alertifyjs'
import { Menu } from './Menu'
import { Field, Input, InputArea, VideoForm } from './Input'

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
                for (const property in selected) {
                  console.log('setting VideoForm', property, selected[property])
                  VideoForm[property](selected[property])
                }
                selected.project = options[i - 1]
                console.log('selected', selected)
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

        m(Input, {name: 'name'}, 'Business Name'),
        m('p', VideoForm.name()),
        m(Input, {name: 'logo'}, 'Logo'),
        m(InputArea, {name: 'address'}, 'Address'),
        m(Input, {name: 'phone'}, 'Phone'),
        m(Input, {name: 'hours'}, 'Hours'),
        m(Input, {name: 'website'}, 'Website'),
        m(InputArea, {name: 'initial'}, 'Initial text'),
        m(InputArea, {name: 'bullets'}, 'Bullets'),
        m(InputArea, {name: 'optional'}, 'Optional'),
        m(InputArea, {name: 'media'}, 'Media'),
        m(InputArea, {name: 'audio'}, 'Audio'),
        m(InputArea, {name: 'call'}, 'Call'),
        // m(TextArea, {name: 'closing'}, 'Closing'),
        m(Color, {name: 'themecolor', value:'#FF0'}, 'Theme Color'),
        m(Color, {name: 'fontcolor', value: '#FFF'}, 'Font Clolor'),
        m(Input, {name: 'font'}, 'Font'),
        m(Input, {name: 'duration'}, 'Duration'),
        m('hr'),
        m('', {style: {'text-align': 'right'}}, [
          m('input', {type: 'submit', name: 'render', value: 'Preview',
            onclick: (e) => {
              e.preventDefault()
              let form = new FormData(document.getElementById('form'))
              let proj = document.getElementById('projectName').value
              console.log('rendering from form', e, form)
              m.request('/formToEdl', {
                method: 'post',
                body: form,
              }).then(e => {
                console.log('rendering', e)
                success(`rendering!`)
                m.route.set(`/otto?project=${proj}`)
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
