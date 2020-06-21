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

export function Form() {
  return {
    view: (vnode) => {
      return m('form.form', {
        action: '/otto/form',
        method: 'POST',
      }, [
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
