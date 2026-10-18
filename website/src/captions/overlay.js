import m from 'mithril'
import { Edl } from '../Video'
import { User } from '../User'
import { Captions, DRAWN } from './store'
import './captions.scss'

/**
 * The caption under the playhead, over the viewer.
 *
 * The preview is a frame the server draws, and drawing captions into every
 * preview frame would cost a request per playhead move. This draws them in
 * the page instead, in the style they will render in -- size relative to the
 * frame, colours, the translucent box, top, centre or bottom -- so editing a
 * caption shows it at once. The render is what the server draws
 * (`utils.captions`); this is a close likeness of it, not a promise.
 *
 * It lies over the viewer rather than in it: the viewer carries the
 * `captioned` class (`captions.scss` makes it the box this is placed in), and
 * this is positioned absolutely, so nothing in the viewer moves for it.
 */

// The share of the viewer a caption is inset by, as the render insets it.
const MARGIN = 0.05
// The render draws its box at 40% opacity (otto's textBox).
const BOX_OPACITY = 0.4

const hex = colour => {
  const digits = String(colour || '').replace('#', '')
  const full = digits.length === 3 ? digits.split('').map(d => d + d).join('') : digits
  const n = parseInt(full, 16)
  return Number.isFinite(n) ? [(n >> 16) & 255, (n >> 8) & 255, n & 255] : [0, 0, 0]
}

/** How tall the viewer is drawn, in pixels, as Head.js sizes it. */
const viewerHeight = () =>
  window.innerHeight * (window.innerWidth > window.innerHeight ? 0.4 : 0.24)

const ACROSS = { left: 'flex-start', center: 'center', right: 'flex-end' }
const DOWN = { top: 'flex-start', center: 'center', bottom: 'flex-end' }

/** The position as (across, down) words. */
const placed = position =>
  Array.isArray(position)
    ? position
    : ['center', position === 'top' || position === 'center' ? position : 'bottom']

/** The class the viewer carries so the overlay can lie over it. */
export const VIEWER_CLASS = 'captioned'

// The project's captions are needed whether or not the panel is open.
const load = () => {
  if (User.loggedIn) Captions.ensure(m.route.param('project'))
}

export const CaptionOverlay = {
  oninit: load,
  onupdate: load,
  view: () => {
    const style = Captions.style || {}
    const shown = Captions.at(Edl.time)
    if (!shown.length) return null
    const height = viewerHeight()
    const size = ((Number(style.fontsize) || DRAWN.fontsize) / 1080) * height
    const [across, down] = placed(style.position || DRAWN.position)
    const bg = style.bg === '' ? null : hex(style.bg || DRAWN.bg)
    const align = { west: 'left', east: 'right' }[style.align] || 'center'
    // Shown whether or not renders draw them -- they are being edited -- but
    // faint when they do not, so the viewer does not promise what the
    // render will leave out.
    const drawn = style.enabled === true
    return m(
      '#caption-overlay',
      {
        'aria-live': 'polite',
        'data-drawn': drawn ? 'true' : 'false',
        title: drawn ? '' : 'Captions are not drawn into renders (see the Captions panel)',
        style: {
          opacity: drawn ? 1 : 0.45,
          justifyContent: DOWN[down] || 'flex-end',
          alignItems: ACROSS[across] || 'center',
          padding: `${height * MARGIN}px 5%`,
        },
      },
      shown.map(caption =>
        m(
          'span.captionline',
          {
            style: {
              fontSize: `${Math.max(8, size)}px`,
              color: style.color || DRAWN.color,
              textAlign: align,
              background: bg ? `rgba(${bg.join(', ')}, ${BOX_OPACITY})` : 'transparent',
            },
          },
          caption.text
        )
      )
    )
  },
}
