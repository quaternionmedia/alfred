import { PanelRegistry } from './registry'
import { LAYOUT_SETTINGS } from './default_layout'

/**
 * The viewer's own arrangement of the workspace: kept, checked, or dropped.
 *
 * Kept in this browser's localStorage, so it is per viewer and per browser,
 * and survives a reload and a new session. The key carries a version: a
 * release whose panels no longer fit an older arrangement moves to a new key
 * rather than reading one it cannot use. Every touch of storage is guarded --
 * a browser can refuse it outright (private browsing, a full quota, a
 * policy), and the workspace then opens as it does the first time.
 *
 * A saved arrangement is read before Golden Layout sees it. Golden Layout
 * throws on a component type nobody registered, and the shell loads the
 * layout while it starts: a layout naming a panel this version lacks would
 * leave a page with no panels. So it is read as plain JSON and loaded only
 * if it is a layout, every panel in it is registered and appears once, under
 * its registry id (find-by-id is how a panel is shown or known to be open),
 * and the timeline -- which cannot be closed -- is in it. Anything else is
 * dropped for the default, and the viewer is told.
 */

export const LAYOUT_KEY = 'alfred.layout.v1'

const CONTAINERS = new Set(['row', 'column', 'stack'])

/**
 * Read saved text: nothing saved, a layout to load, or why not.
 *
 * @param {string | null | undefined} raw
 * @param {readonly import('./registry').PanelDefinition[]} [panels]
 * @returns {{kind: 'none'} | {kind: 'usable', config: object} | {kind: 'unusable', why: string}}
 */
export function readSavedLayout(raw, panels = PanelRegistry.all()) {
  if (raw === null || raw === undefined || raw === '') return { kind: 'none' }
  let config
  try {
    config = JSON.parse(raw)
  } catch (e) {
    return { kind: 'unusable', why: 'it is not JSON' }
  }
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    return { kind: 'unusable', why: 'it is not a layout' }
  }
  if (!config.root || typeof config.root !== 'object' || Array.isArray(config.root)) {
    return { kind: 'unusable', why: 'it has no panels in it' }
  }
  if (Array.isArray(config.openPopouts) && config.openPopouts.length) {
    return { kind: 'unusable', why: 'it has panels in windows of their own' }
  }

  const known = new Map(panels.map(panel => [panel.id, panel]))
  const seen = []
  const problem = check(config.root, known, seen)
  if (problem) return { kind: 'unusable', why: problem }

  const twice = seen.filter((id, i) => seen.indexOf(id) !== i)
  if (twice.length) return { kind: 'unusable', why: `it shows ${twice[0]} twice` }
  const missing = panels.find(panel => panel.closable === false && !seen.includes(panel.id))
  if (missing) return { kind: 'unusable', why: `it has no ${missing.title}` }

  return {
    kind: 'usable',
    config: {
      // Today's settings over whatever was saved with it: they are the
      // app's, not the viewer's arrangement.
      ...LAYOUT_SETTINGS,
      root: config.root,
      openPopouts: [],
    },
  }
}

/** Why `item` cannot be loaded, or nothing; collects the panel ids it names. */
function check(item, known, seen) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) return 'it has an item that is not one'
  if (item.type === 'component') {
    const panel = known.get(item.componentType)
    if (!panel) return `it names ${JSON.stringify(item.componentType)}, which this version does not have`
    if (item.id !== panel.id) return `its ${panel.title} panel is not under its id`
    // The registry's title and closability, not the saved ones.
    item.title = panel.title
    item.isClosable = panel.closable !== false
    seen.push(panel.id)
    return null
  }
  if (!CONTAINERS.has(item.type)) return `it has an item of a kind Golden Layout does not know (${JSON.stringify(item.type)})`
  if (!Array.isArray(item.content) || item.content.length === 0) return `it has an empty ${item.type}`
  for (const child of item.content) {
    if (item.type === 'stack' && (!child || child.type !== 'component')) return 'it has a stack holding something other than panels'
    const problem = check(child, known, seen)
    if (problem) return problem
  }
  return null
}

/** The saved text, or null when there is none or storage is refused. */
export function savedLayoutText() {
  try {
    return window.localStorage.getItem(LAYOUT_KEY)
  } catch (e) {
    return null
  }
}

/** Keep `config` as this viewer's arrangement. False when storage refuses. */
export function keepLayout(config) {
  try {
    window.localStorage.setItem(LAYOUT_KEY, JSON.stringify(config))
    return true
  } catch (e) {
    return false
  }
}

/** Forget the saved arrangement. */
export function forgetLayout() {
  try {
    window.localStorage.removeItem(LAYOUT_KEY)
  } catch (e) {
    // Refused: there is nothing this page can do about it, and nothing lost.
  }
}
