import m from 'mithril'
import { Edl } from './Video'
import { TemplatePreview, templatePreviewUrl } from './Preview'
import Bin from './Bin'

/** Two frame URLs for the same template and settings, at any time. */
const sameSettings = (a, b) =>
  Boolean(a && b) && a.replace(/&t=[^&]*$/, '') === b.replace(/&t=[^&]*$/, '')

/**
 * The settings of the template clip under the playhead.
 *
 * A template clip's text, length and colours could not be changed anywhere.
 * The Template "editor" on the Source stage is a read-only view of a
 * project's form logic, and the text on a clip was a contenteditable that
 * showed "Hello, world" twice (see OttoTimeline's Template).
 *
 * This edits the clip in place. The viewer's frame URL is built from the
 * clip's data, so every change is rendered by the server, and that is the
 * validation: a template that cannot render what it was given answers 422
 * with the reason, and the reason is shown here, next to the fields, rather
 * than only where the frame would have been.
 *
 * Fields are offered for what the template takes, by the parameter list
 * `GET /templates` publishes -- `makeColor` takes a colour and no text, so it
 * is not offered text -- and only the parameters `TemplateData` carries.
 */

const COLOURS = [
  { key: 'color', label: 'Colour' },
  { key: 'themecolor', label: 'Theme colour' },
  { key: 'bg', label: 'Background' },
]

// Offered when the template's parameters are not known yet (the bin has not
// loaded): everything TemplateData carries that this form edits.
const EVERYTHING = ['text', 'color', 'themecolor', 'bg']

const SHORTEST = 0.1

/** Write one field of a clip's data; '' or null removes it, back to the template's default. */
function setData(clip, key, value) {
  const data = { ...(clip.data || {}) }
  if (value === null || value === undefined || value === '') delete data[key]
  else data[key] = value
  clip.data = data
}

/** A colour as `#rrggbb` for the swatch, or null if the browser cannot read it as one. */
function swatchValue(colour) {
  if (!colour) return null
  if (/^#[0-9a-f]{6}$/i.test(colour)) return colour.toLowerCase()
  const ctx = document.createElement('canvas').getContext('2d')
  if (!ctx) return null
  // A sentinel first: an unreadable colour leaves fillStyle unchanged.
  ctx.fillStyle = '#010203'
  ctx.fillStyle = String(colour)
  const read = ctx.fillStyle
  if (read === '#010203' && !/^#010203$/i.test(colour)) return null
  return /^#[0-9a-f]{6}$/i.test(read) ? read : null
}

export const TemplateParams = () => {
  // What is being typed into Duration, kept until the field loses focus.
  // The input is controlled, and mithril writes `value` back whenever it
  // differs from what is typed -- so "1." or an emptied field, on the way to
  // a real number, would be replaced mid-keystroke by the clip's duration.
  let draft = null

  const colourField = (clip, { key, label }) => {
    const value = (clip.data && clip.data[key]) || ''
    const swatch = swatchValue(value)
    return m('.paramcolour', [
      m('label', { for: `param-${key}` }, label),
      m('input.swatch', {
        type: 'color',
        class: swatch ? '' : 'unset',
        value: swatch || '#000000',
        'aria-label': `${label} swatch`,
        oninput: e => setData(clip, key, e.target.value),
      }),
      m(`input#param-${key}`, {
        type: 'text',
        value,
        placeholder: 'template default',
        spellcheck: false,
        // Not trimmed as it is typed: the field is controlled, so trimming
        // would delete the space in "rgb(0, 0, 0)" while it was being typed.
        oninput: e => setData(clip, key, e.target.value.trim() ? e.target.value : null),
      }),
      value
        ? m(
            'button.paramreset',
            {
              type: 'button',
              title: `Use the template's own ${label.toLowerCase()}`,
              onclick: () => setData(clip, key, null),
            },
            'Default'
          )
        : null,
    ])
  }

  return {
    view: () => {
      const index = Edl.current
      const clip = Edl.edl[index]
      if (!clip || clip.type !== 'template') return null

      const described = Bin.templates.find(t => t.name === clip.name)
      const takes =
        described && Array.isArray(described.parameters) ? described.parameters : EVERYTHING
      const data = clip.data || {}
      const duration = draft && draft.clip === clip ? draft.value : clip.duration

      // A group, not a <form>: style.css styles every form for the project
      // form on the Render stage -- a heavy border, 1em margins on every
      // input, six-line textareas -- and nothing here is submitted anyway.
      return m(
        '.templateparams#template-params',
        { role: 'group', 'aria-label': `Settings for the ${clip.name} clip` },
        [
          m('h4', [clip.name, m('span.paramclip', ` · clip ${index + 1}`)]),

          takes.includes('text')
            ? [
                m('label', { for: 'param-text' }, 'Text'),
                m('textarea#param-text', {
                  rows: 2,
                  value: data.text || '',
                  oninput: e => setData(clip, 'text', e.target.value),
                }),
              ]
            : null,

          m('label', { for: 'param-duration' }, 'Duration (seconds)'),
          m('input#param-duration', {
            type: 'number',
            min: SHORTEST,
            step: 0.1,
            value: duration,
            oninput: e => {
              draft = { clip, value: e.target.value }
              const seconds = Number(e.target.value)
              if (e.target.value !== '' && seconds >= SHORTEST) clip.duration = seconds
            },
            onblur: () => {
              draft = null
            },
          }),

          COLOURS.filter(c => takes.includes(c.key)).map(c => colourField(clip, c)),

          // The server's reason, in words, where the settings are -- when it
          // is about these settings. The verdict is on whichever frame the
          // viewer asked for last, which may be another clip's, or these
          // settings before the last keystroke.
          TemplatePreview.problem && sameSettings(TemplatePreview.src, templatePreviewUrl(clip))
            ? m('p.paramproblem#param-problem', { role: 'alert' }, TemplatePreview.problem)
            : null,
        ]
      )
    },
  }
}
