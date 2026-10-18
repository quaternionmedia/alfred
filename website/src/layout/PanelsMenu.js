import m from 'mithril'
import { PanelRegistry } from './registry'
import { Workspace } from './workspace'

/**
 * The Panels menu: every panel, and the default arrangement.
 *
 * Choosing a panel shows it: brought to the front of its stack if it is in
 * the workspace, put back in its place if it was closed -- never a second
 * copy. A closed one says so. Reset layout is the arrangement the workspace
 * first opened with, and forgets the saved one.
 *
 * A menu button in the WAI-ARIA sense: Enter, Space or the arrow keys open
 * it with the focus on an item, the arrow keys, Home and End move between
 * items, Escape closes it and returns the focus to the button, and so does a
 * click anywhere else.
 */
export const PanelsMenu = () => {
  let open = false
  let button = null
  let list = null
  let focusOnOpen = null
  let teardown = null

  const items = () => (list ? [...list.querySelectorAll('[role="menuitem"]')] : [])

  const close = ({ refocus = false } = {}) => {
    if (!open) return
    open = false
    if (teardown) teardown()
    teardown = null
    if (refocus && button) button.focus()
    m.redraw()
  }

  const show = which => {
    open = true
    focusOnOpen = which
  }

  // The focus goes where the choice took effect: the panel's own tab, once
  // it has been drawn and named; the button again after a reset.
  const choosePanel = id => {
    Workspace.showPanel(id, { follow: true })
    close()
    setTimeout(() => {
      const tab = document.getElementById(`paneltab-${id}`)
      if (tab) tab.focus()
    })
  }

  const chooseReset = () => {
    Workspace.resetLayout()
    close({ refocus: true })
  }

  const onButtonKeydown = e => {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      show('first')
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      show('last')
    }
  }

  const onMenuKeydown = e => {
    const all = items()
    const at = all.indexOf(document.activeElement)
    const next = {
      ArrowDown: all[(at + 1) % all.length],
      ArrowUp: all[(at - 1 + all.length) % all.length],
      Home: all[0],
      End: all[all.length - 1],
    }[e.key]
    if (next) {
      e.preventDefault()
      next.focus()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      close({ refocus: true })
    } else if (e.key === 'Tab') {
      close()
    }
    // Nothing in the menu is the page's to handle: Space is not play here.
    e.stopPropagation()
  }

  const item = (attrs, label) =>
    m('li', { role: 'none' }, m('button.panelsitem', { type: 'button', role: 'menuitem', ...attrs }, label))

  return {
    oncreate: vnode => {
      button = vnode.dom.querySelector('#panels-button')
    },
    onupdate: vnode => {
      list = vnode.dom.querySelector('#panels-menu')
      if (open && list && focusOnOpen) {
        const all = items()
        const target = focusOnOpen === 'last' ? all[all.length - 1] : all[0]
        focusOnOpen = null
        if (target) target.focus()
      }
      if (open && list && !teardown) {
        // Armed after the click that opened it has finished, or that same
        // click would close it again.
        const outside = e => {
          if (!vnode.dom.contains(e.target)) close()
        }
        const timer = setTimeout(() => document.addEventListener('pointerdown', outside, true))
        teardown = () => {
          clearTimeout(timer)
          document.removeEventListener('pointerdown', outside, true)
        }
      }
    },
    onremove: () => {
      if (teardown) teardown()
      teardown = null
    },
    view: () =>
      m('.panelsmenu', [
        m(
          'button#panels-button.panelsbutton',
          {
            type: 'button',
            'aria-haspopup': 'menu',
            'aria-expanded': open ? 'true' : 'false',
            'aria-controls': 'panels-menu',
            title: 'Show a panel, bring back a closed one, or reset the layout',
            onclick: () => (open ? close() : show('first')),
            onkeydown: onButtonKeydown,
          },
          [m('i.material-icons', { 'aria-hidden': 'true' }, 'view_quilt'), m('span', 'Panels')]
        ),
        open
          ? m(
              'ul#panels-menu.panelslist',
              { role: 'menu', 'aria-label': 'Panels', onkeydown: onMenuKeydown },
              [
                PanelRegistry.all().map(panel => {
                  const closed = !Workspace.isOpen(panel.id)
                  return item(
                    {
                      'data-panel': panel.id,
                      class: closed ? 'closed' : '',
                      onclick: () => choosePanel(panel.id),
                    },
                    [
                      m('span.panelsname', panel.title),
                      closed ? m('span.panelsstate', 'closed') : null,
                    ]
                  )
                }),
                m('li.panelsdivider', { role: 'separator' }),
                item(
                  { id: 'reset-layout', onclick: chooseReset },
                  'Reset layout'
                ),
              ]
            )
          : null,
      ]),
  }
}
