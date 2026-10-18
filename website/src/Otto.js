import m from 'mithril'
import './styles/editor.scss'
import { User } from './User'
import { StackedFlow } from './layout/flow'

/**
 * The editor: the route `/` (and `/otto`) draws.
 *
 * The timeline is the subject; everything else adorns it. What used to be
 * drawn here region by region -- the stage panels, the viewer and its
 * transport, the timeline with its tools and its bin -- is a set of panels
 * now (panels/), each one module, and a layout (layout/) decides where they
 * sit.
 */
export var Otto = {
  // Re-checked on every mount, not only at boot.
  //
  // A single check after boot covered whichever route happened to resolve
  // first and left the others open -- an anonymous visitor reached #!/otto and
  // stayed. This runs on each mount and does nothing until boot has answered.
  oninit: () => User.requireSession(),
  view: () => m(StackedFlow),
}
