import m from 'mithril'
import { GoldenLayout, LayoutConfig } from 'golden-layout'
import { message } from 'alertifyjs'
import { PanelRegistry, STAGE_PANELS } from './registry'
import { DEFAULT_LAYOUT, REOPEN, panelConfig } from './default_layout'
import { forgetLayout, keepLayout, readSavedLayout, savedLayoutText } from './saved_layout'
import { PanelHosts } from './hosts'
import { Flow } from '../Stages'
import { escapeHtml } from '../Problem'

/**
 * The desktop workspace: the editor's panels in a Golden Layout dock.
 *
 * One at a time, built in the element the shell gives it (`create`) and torn
 * down when the shell takes it away (`destroy`). Everything else here is
 * what the rest of the page can ask of it:
 *
 *   showPanel(id)   bring a panel to the front of its stack -- reopening it,
 *                   in its place, if it was closed; never a second copy
 *   showStage(id)   bring a stage's panels forward: what `?stage=` and the
 *                   rail ask for
 *   isOpen(id)      whether a panel is in the layout
 *   resetLayout()   the default arrangement, and forget the saved one
 *
 * A panel is shown with `Stack.setActiveComponentItem`. `ComponentItem.focus()`
 * marks an item focused and leaves its stack showing whichever tab it showed;
 * codecartographer's first attempt called it, and the panel stayed behind.
 */

let gl = null
let host = null
let saveTimer = null
// The `?stage=` last brought forward, so a redraw does not bring it forward
// again over whatever the viewer has chosen since.
let appliedStage = null
let decorating = false

/** Draw panel `definition` in `container`, Golden Layout's box for it. */
function bind(definition, container) {
  // The registry's title, whatever the layout it was loaded from says.
  container.setTitle(definition.title)
  PanelHosts.place(definition.id, container.element, { draw: !definition.whileShown })
  if (definition.whileShown) {
    // Shown with its size known, which is also how a panel first appears.
    container.on('show', () => PanelHosts.draw(definition.id))
    container.on('hide', () => PanelHosts.erase(definition.id))
  }
  container.on('beforeComponentRelease', () => PanelHosts.lift(definition.id))
  return { panel: definition.id }
}

/** The saved arrangement if it can be used, else the default. */
function load() {
  const saved = readSavedLayout(savedLayoutText())
  if (saved.kind === 'unusable') drop(saved.why)
  const config = saved.kind === 'usable' ? saved.config : DEFAULT_LAYOUT
  try {
    gl.loadLayout(config)
  } catch (err) {
    // It passed the check and Golden Layout refused it anyway. Boot the
    // default rather than a page with no panels; the default itself failing
    // is a bug, and throws.
    if (config === DEFAULT_LAYOUT) throw err
    drop(`Golden Layout refused it (${err && err.message ? err.message : err})`)
    gl.loadLayout(DEFAULT_LAYOUT)
  }
}

/** Forget the saved arrangement, and say why the default is showing. */
function drop(why) {
  forgetLayout()
  message(
    `Your arrangement of the panels could not be used, so the default is showing: ${escapeHtml(why)}.`,
    8
  )
}

function scheduleSave() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 250)
}

function save() {
  clearTimeout(saveTimer)
  saveTimer = null
  if (!gl || !gl.isInitialised) return
  try {
    keepLayout(LayoutConfig.fromResolved(gl.saveLayout()))
  } catch (e) {
    // Caught mid-change; the next change saves it.
  }
}

/**
 * Put closed panel `id` back: beside the panels it shares a stack with by
 * default, else in its own stack above or below the panel it sits by, else
 * where Golden Layout puts things.
 */
function reopen(id) {
  const config = panelConfig(id)
  const rule = REOPEN[id] || { tabs: [], beside: [], at: 'after' }
  for (const sibling of rule.tabs) {
    const item = gl.findFirstComponentItemById(sibling)
    if (item && item.parent && item.parent.isStack) {
      item.parent.addItem(config)
      return gl.findFirstComponentItemById(id)
    }
  }
  for (const neighbour of rule.beside) {
    const item = gl.findFirstComponentItemById(neighbour)
    const stack = item && item.parent
    if (!stack || !stack.isStack) continue
    const column = stack.parent
    if (column && column.isColumn) {
      const at = column.contentItems.indexOf(stack) + (rule.at === 'after' ? 1 : 0)
      column.addItem({ type: 'stack', content: [config] }, at)
      return gl.findFirstComponentItemById(id)
    }
    // Its column has gone: Golden Layout folds a column away when one stack
    // is left in it. Split that stack into a column again, as dropping a tab
    // on its edge would -- on the layout as saved, loaded back, so nothing
    // but Golden Layout's public calls is needed. The panels are not built
    // again (hosts.js); they are only placed again.
    const layout = LayoutConfig.fromResolved(gl.saveLayout())
    if (splitAround(layout, neighbour, config, rule.at)) {
      PanelHosts.rebuild()
      gl.loadLayout(layout)
      return gl.findFirstComponentItemById(id)
    }
  }
  gl.addItem(config)
  return gl.findFirstComponentItemById(id)
}

/**
 * In `layout`, replace the stack holding panel `anchor` with a column of it
 * and a new stack of `entry`, the new one `at` 'before' (above) or 'after'
 * (below). False when the anchor is not found.
 */
function splitAround(layout, anchor, entry, at) {
  const holds = item =>
    item && item.type === 'stack' && (item.content || []).some(c => c.componentType === anchor)
  const visit = (parent, key) => {
    const item = parent[key]
    if (!item || typeof item !== 'object') return false
    if (holds(item)) {
      const added = { type: 'stack', size: '40%', content: [entry] }
      const kept = { ...item, size: '60%' }
      parent[key] = {
        type: 'column',
        size: item.size,
        content: at === 'before' ? [added, kept] : [kept, added],
      }
      return true
    }
    const content = item.content || []
    for (let i = 0; i < content.length; i++) if (visit(content, i)) return true
    return false
  }
  return visit(layout, 'root')
}

/** The stage a tab belongs to, in the address: choosing a panel is choosing its stage. */
function followTab(id) {
  const definition = PanelRegistry.get(id)
  if (!definition || Flow.stage() === definition.stage) return
  appliedStage = definition.stage
  m.route.set(
    m.route.get().split('?')[0],
    { ...m.route.param(), stage: definition.stage },
    // Replaced, not pushed: a tab chosen is not a page visited, and Back
    // walking through every tab clicked would be a strange history.
    { replace: true }
  )
}

function onClick(e) {
  const tab = e.target.closest && e.target.closest('.lm_tab[data-panel]')
  if (!tab || e.target.closest('.lm_close_tab')) return
  followTab(tab.dataset.panel)
}

/**
 * The keyboard on the dock: a tab is a tab, and the controls are buttons.
 *
 * Enter or Space shows the focused tab's panel; the arrow keys, Home and End
 * move along a stack's tabs; Delete closes a panel that can be closed. Kept
 * from the page's own shortcuts -- Space is play and pause, the arrows seek
 * -- which would otherwise act on the same key.
 */
function onKeydown(e) {
  const tab = e.target.closest && e.target.closest('.lm_tab[data-panel]')
  if (tab) {
    const id = tab.dataset.panel
    const tabs = [...tab.parentElement.querySelectorAll('.lm_tab[data-panel]')]
    const at = tabs.indexOf(tab)
    const move = {
      ArrowRight: tabs[(at + 1) % tabs.length],
      ArrowDown: tabs[(at + 1) % tabs.length],
      ArrowLeft: tabs[(at - 1 + tabs.length) % tabs.length],
      ArrowUp: tabs[(at - 1 + tabs.length) % tabs.length],
      Home: tabs[0],
      End: tabs[tabs.length - 1],
    }[e.key]
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      e.stopPropagation()
      Workspace.showPanel(id, { follow: true })
      // Golden Layout puts a stack's tabs back in their strip when one is
      // chosen, and an element put back loses the focus: the next key would
      // reach the page instead of the tab it was pressed on.
      tab.focus()
    } else if (move) {
      e.preventDefault()
      e.stopPropagation()
      move.focus()
    } else if (e.key === 'Delete') {
      const item = gl && gl.findFirstComponentItemById(id)
      if (item && item.isClosable) {
        e.preventDefault()
        e.stopPropagation()
        item.close()
      }
    }
    return
  }
  const control = e.target.closest && e.target.closest('.lm_controls > [role="button"]')
  if (control && (e.key === 'Enter' || e.key === ' ')) {
    e.preventDefault()
    e.stopPropagation()
    control.click()
  }
}

/** Roles, names and tab stops for what Golden Layout draws, which has none. */
function decorate() {
  decorating = false
  if (!gl || !gl.rootItem) return
  const visit = item => {
    if (!item) return
    if (item.isComponent) decorateComponent(item)
    for (const child of item.contentItems) visit(child)
  }
  visit(gl.rootItem)
  for (const control of host.querySelectorAll('.lm_controls > *')) {
    control.setAttribute('role', 'button')
    control.tabIndex = 0
  }
}

function decorateComponent(item) {
  const definition = PanelRegistry.get(item.id)
  if (!definition) return
  const id = definition.id
  const stack = item.parent
  const front = !stack || !stack.isStack || stack.getActiveComponentItem() === item
  const tab = item.tab && item.tab.element
  if (tab) {
    tab.id = `paneltab-${id}`
    tab.dataset.panel = id
    tab.setAttribute('role', 'tab')
    tab.setAttribute('aria-label', definition.title)
    tab.setAttribute('aria-selected', front ? 'true' : 'false')
    tab.setAttribute('aria-controls', `panelbody-${id}`)
    if (item.isClosable) tab.setAttribute('aria-keyshortcuts', 'Delete')
    tab.tabIndex = front ? 0 : -1
    if (tab.parentElement) {
      tab.parentElement.setAttribute('role', 'tablist')
      tab.parentElement.setAttribute('aria-label', 'Panels')
    }
    const close = tab.querySelector('.lm_close_tab')
    if (close) {
      // The ✕ is the mouse's way to close; the keyboard's is Delete on the
      // tab, so the ✕ is not a second stop, and not read out as part of the
      // tab's name.
      close.setAttribute('aria-hidden', 'true')
      close.title = `Close ${definition.title}`
    }
  }
  const body = item.container && item.container.element
  if (body) {
    body.id = `panelbody-${id}`
    body.setAttribute('role', 'tabpanel')
    body.setAttribute('aria-labelledby', `paneltab-${id}`)
  }
}

function queueDecorate() {
  if (decorating) return
  decorating = true
  Promise.resolve().then(decorate)
}

export const Workspace = {
  /** Whether a workspace is on screen. */
  active: () => gl !== null,

  /** Build the workspace in `element`, from the saved arrangement or the default. */
  create(element) {
    host = element
    gl = new GoldenLayout(element)
    // Follow the element's size: the window, and the draft notice above it.
    gl.resizeWithContainerAutomatically = true
    for (const definition of PanelRegistry.all()) {
      gl.registerComponentFactoryFunction(definition.id, container => bind(definition, container))
    }
    gl.on('stateChanged', () => {
      scheduleSave()
      queueDecorate()
    })
    gl.on('activeContentItemChanged', queueDecorate)
    gl.on('tabCreated', queueDecorate)
    element.addEventListener('click', onClick)
    element.addEventListener('keydown', onKeydown)
    load()
    appliedStage = null
    Workspace.followRoute()
    queueDecorate()
  },

  /** Take the workspace down, keeping the arrangement it had. */
  destroy() {
    if (!gl) return
    if (saveTimer) save()
    host.removeEventListener('click', onClick)
    host.removeEventListener('keydown', onKeydown)
    gl.destroy()
    gl = null
    host = null
  },

  /** Bring the stage named in the address forward, when it changes. */
  followRoute() {
    if (!gl) return
    const stage = m.route.param('stage')
    if (stage === appliedStage) return
    appliedStage = stage
    if (stage && STAGE_PANELS[stage]) Workspace.showStage(stage)
  },

  /**
   * Bring stage `stage`'s panels forward, reopening any that were closed;
   * the panel the stage is about is the one in front where two share a
   * stack, and has the focus.
   */
  showStage(stage) {
    const ids = STAGE_PANELS[stage]
    if (!gl || !ids) return
    appliedStage = stage
    for (const id of [...ids].reverse()) Workspace.showPanel(id, { focus: id === ids[0] })
  },

  /**
   * Bring panel `id` to the front of its stack, reopening it if it was
   * closed. `follow` is a panel the viewer chose, as from the Panels menu:
   * the address says its stage, as choosing its tab does.
   */
  showPanel(id, { focus = true, follow = false } = {}) {
    if (!gl || !PanelRegistry.get(id)) return
    const item = gl.findFirstComponentItemById(id) || reopen(id)
    if (!item) return
    const stack = item.parent
    // A maximised stack hides the rest; a panel elsewhere is not shown by
    // being brought to the front of a stack nobody can see.
    const maximised = gl.maximisedStack
    if (maximised && maximised !== stack) maximised.minimise()
    if (stack && typeof stack.setActiveComponentItem === 'function') {
      stack.setActiveComponentItem(item, focus)
    }
    queueDecorate()
    if (follow) followTab(id)
  },

  /** Whether panel `id` is in the layout. */
  isOpen: id => Boolean(gl && gl.findFirstComponentItemById(id)),

  /** The default arrangement, with the saved one forgotten. */
  resetLayout() {
    if (!gl) return
    clearTimeout(saveTimer)
    saveTimer = null
    forgetLayout()
    // Every panel is released and bound again; none of them starts over.
    PanelHosts.rebuild()
    gl.loadLayout(DEFAULT_LAYOUT)
    appliedStage = null
    Workspace.followRoute()
    queueDecorate()
  },
}

// The rail, and anything else that asks the flow for a stage, brings it
// forward here -- the stage already in the address included, since its panel
// may have been closed or put behind another since.
Flow.followers.push(stage => Workspace.showStage(stage))
