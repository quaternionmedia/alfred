import m from 'mithril'
import { Menu } from './Menu'

export function Dropdown() {
  return {
    view: (vnode) => {
      return m('select', [
        m('option', {value: ''}, ''),
        vnode.children.map( opt => {
          return m('option', {
          value: opt['name']
        }, opt['name'])})
      ])
    }
  }
}

export function Form() {

  var options = []
  var selected = null

  function Text() {
    return {
      view: (vnode) => {
        return m('', {}, [
          m('label.formlabel', {
            for: vnode.attrs.name
          }, vnode.children),
          m('input', {
            ...vnode.attrs,
            value: selected ? selected[vnode.attrs.name] : null
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
            value: selected ? selected[vnode.attrs.name] : null
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
            value: selected ? selected[vnode.attrs.name] : null
          })
        ])
      }
    }
  }

  return {
    oninit: (vnode) => {
      m.request('/projects').then(e => {
        options = JSON.parse(e)
        console.log('projects', options)
      })
    },

    view: (vnode) => {
      return m('form.form', {
        action: '/otto/form',
        method: 'POST',
        onchange: e => {
          const i = e.target.selectedIndex
          console.log('form res', options, i)
          if (options && i) {
            m.request(`/project/${options[i - 1].name}`).then(res => {
              selected = res
              selected.name = options[i - 1].name
            })
          }
        }
      }, [
        m(Dropdown, options),
        m('br'),
        m(Text, {name: 'project'}, 'Project Name'),
        m('', {style: {'text-align': 'right'}}, [
          m('input', {type: 'submit', name: 'save', value: 'save'},),
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
        m(TextArea, {name: 'AUDIO'}, 'Audio'),
        m(TextArea, {name: 'MEDIA'}, 'Media'),
        m(TextArea, {name: 'CALL'}, 'Call'),
        // m(TextArea, {name: 'CLOSING'}, 'Closing'),
        m(Color, {name: 'FONTCOLOR'}, 'Font Clolor'),
        m(Color, {name: 'THEMECOLOR'}, 'Theme Color'),
        m(Text, {name: 'FONT'}, 'Font'),
        m(Text, {name: 'DURATION'}, 'Duration'),
        m('', {style: {'text-align': 'right'}}, [
          m('input', {type: 'submit', name: 'render', value: 'render'}, )
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
