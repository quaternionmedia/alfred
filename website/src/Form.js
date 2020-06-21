import m from 'mithril'
import { Menu } from './Menu'

export function Text() {
  return {
    view: (vnode) => {
      return m('', {}, [
        m('label.formlabel', {
          for: vnode.attrs.name
        }, vnode.children),
        m('input', {
          ...vnode.attrs
        })
      ])
    }
  }
}

export function Dropdown() {
  return {
    view: (vnode) => {
      return m('select', [
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
          console.log('form res', options, e.target.selectedIndex)
          if (options) {
            m.request(`/example/${options[e.target.selectedIndex].name}`).then(res => {
              selected = res
          })
        }
        }
      }, [
        m(Dropdown, options),
        m(Text, {name: 'NAME', value: selected ? selected.NAME : null}, 'Business Name'),
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
        m('input', {type: 'submit'})
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
