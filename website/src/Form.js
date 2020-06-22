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

  return {
    oninit: (vnode) => {
      m.request('/examples').then(e => {
        options = JSON.parse(e)
        console.log('examples', options)
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
            m.request(`/example/${options[i - 1].name}`).then(res => {
              selected = res
              selected.name = options[i - 1].name
            })
          }
        }
      }, [
        m(Dropdown, options),
        m('br'),
        m('label', {for: 'project'}, 'Project Name'),
        m('input', {name: 'project', value: selected ? selected.name: null}),
        m('input', {type: 'submit', name: 'save', value: 'save'},),
        m('hr'),
        m(Text, {name: 'NAME'}, 'Business Name'),
        m(Text, {name: 'LOGO'}, 'Logo'),
        m(Text, {name: 'ADDRESS'}, 'Address'),
        m(Text, {name: 'PHONE'}, 'Phone'),
        m(Text, {name: 'HOURS'}, 'Hours'),
        m(Text, {name: 'WEBSITE'}, 'Website'),
        m(Text, {name: 'INITIAL'}, 'Initial text'),
        m(Text, {name: 'BULLETS'}, 'Bullets'),
        m(Text, {name: 'OPTIONAL'}, 'Optional'),
        m(Text, {name: 'AUDIO'}, 'Audio'),
        m(Text, {name: 'MEDIA'}, 'Media'),
        m(Text, {name: 'CALL'}, 'Call'),
        m(Text, {name: 'CLOSING'}, 'Closing'),
        m(Text, {name: 'FONTCOLOR'}, 'Font Clolor'),
        m(Text, {name: 'THEMECOLOR'}, 'Theme Color'),
        m(Text, {name: 'FONT'}, 'Font'),
        m(Text, {name: 'DURATION'}, 'Duration'),
        m('input', {type: 'submit', name: 'render', value: 'render'}, )
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
