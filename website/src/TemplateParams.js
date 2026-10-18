import m from 'mithril'
import { Edl } from './Video'
import { TemplatePreview, templatePreviewUrl } from './Preview'
import Bin from './Bin'
import { auth } from './Login'
import { User } from './User'
import { SHORTEST, setLength } from './Timing'

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
 * `GET /templates` publishes -- `makeColor` takes a colour and a position and
 * no text, so it is offered those -- and only for parameters `TemplateData`
 * carries that make sense as a form field: text, colours, the font and its
 * size, how text is aligned in its box, and where the template sits in the
 * frame. (`textsize`, `method` and `fxs` are left to projects that build
 * their clips from logic.)
 */

const COLOURS = [
  { key: 'color', label: 'Colour' },
  { key: 'themecolor', label: 'Theme colour' },
  { key: 'bg', label: 'Background' },
]

// How text sits in its box: ImageMagick's gravity, which the text templates
// hand to it as `align`.
const ALIGNMENTS = [
  ['center', 'Centre'],
  ['West', 'Left'],
  ['East', 'Right'],
  ['North', 'Top'],
  ['South', 'Bottom'],
  ['NorthWest', 'Top left'],
  ['NorthEast', 'Top right'],
  ['SouthWest', 'Bottom left'],
  ['SouthEast', 'Bottom right'],
]

// Where the template sits in the frame: the names a clip can be placed by.
// A position given as coordinates -- a project's logic can write one -- is
// kept as it is and shown as such; the form does not offer to type one.
const POSITIONS = [
  ['center', 'Centre'],
  ['top', 'Top'],
  ['bottom', 'Bottom'],
  ['left', 'Left'],
  ['right', 'Right'],
]

// Offered when the template's parameters are not known yet (the bin has not
// loaded): everything TemplateData carries that this form edits.
const EVERYTHING = ['text', 'color', 'themecolor', 'bg', 'font', 'fontsize', 'align', 'position']

// A select's value for "leave what the clip already has".
const AS_SET = '__as-set__'

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

/**
 * The fonts this server can draw text in (`GET /fonts`), asked for once, when
 * a template that takes a font is first shown. Until they arrive -- or if the
 * server cannot say -- the font field offers the template's default and
 * whatever the clip already names.
 */
export const Fonts = {
  list: [],
  asked: false,

  want: () => {
    if (Fonts.asked || !User.loggedIn) return
    Fonts.asked = true
    auth('/fonts')
      .then(list => {
        Fonts.list = (Array.isArray(list) ? list : [])
          .filter(name => typeof name === 'string' && name)
          .sort((a, b) => a.localeCompare(b))
      })
      .catch(err => {
        console.error('could not list the fonts', err)
        // Asked again the next time a font field is shown.
        setTimeout(() => (Fonts.asked = false), 10000)
      })
  },
}

export const TemplateParams = () => {
  // What is being typed into a number field, kept until the field loses
  // focus. The inputs are controlled, and mithril writes `value` back
  // whenever it differs from what is typed -- so "1." or an emptied field, on
  // the way to a real number, would be replaced mid-keystroke by the clip's.
  let draft = null
  const typed = (clip, key, stored) =>
    draft && draft.clip === clip && draft.key === key ? draft.value : stored

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

  /**
   * A choice among `options` ([value, label] pairs), or the template's own.
   * A value the clip already has that is not among them -- written by a
   * project's logic, or a font this server lacks -- is kept and shown, not
   * silently replaced by the first option.
   */
  const choiceField = (clip, key, label, options) => {
    const current = clip.data ? clip.data[key] : undefined
    const unset = current === undefined || current === null || current === ''
    const listed = unset || options.some(([value]) => value === current)
    return [
      m('label', { for: `param-${key}` }, label),
      m(
        `select#param-${key}`,
        {
          value: unset ? '' : listed ? current : AS_SET,
          onchange: e => {
            if (e.target.value === AS_SET) return
            setData(clip, key, e.target.value || null)
          },
        },
        [
          m('option', { value: '' }, 'Template default'),
          listed ? null : m('option', { value: AS_SET }, `As set: ${String(current)}`),
          options.map(([value, text]) => m('option', { value }, text)),
        ]
      ),
    ]
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
      if (takes.includes('font')) Fonts.want()

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
            value: typed(clip, 'duration', clip.duration),
            oninput: e => {
              draft = { clip, key: 'duration', value: e.target.value }
              const seconds = Number(e.target.value)
              // Through the clip's window (Timing.js): the continuing half of
              // a cut template has an out-point, and it moves with the length.
              if (e.target.value !== '' && seconds >= SHORTEST) setLength(clip, seconds)
            },
            onblur: () => {
              draft = null
            },
          }),

          takes.includes('font')
            ? choiceField(
                clip,
                'font',
                'Font',
                Fonts.list.map(name => [name, name.replace(/-/g, ' ')])
              )
            : null,

          takes.includes('fontsize')
            ? [
                m('label', { for: 'param-fontsize' }, 'Font size'),
                m('input#param-fontsize', {
                  type: 'number',
                  min: 1,
                  step: 1,
                  placeholder: 'template default',
                  value: typed(clip, 'fontsize', data.fontsize == null ? '' : data.fontsize),
                  oninput: e => {
                    draft = { clip, key: 'fontsize', value: e.target.value }
                    const size = Number(e.target.value)
                    // Empty is the template's own size; a size it cannot use
                    // is the server's to refuse, beside these fields.
                    if (e.target.value === '') setData(clip, 'fontsize', null)
                    else if (Number.isFinite(size) && size > 0) setData(clip, 'fontsize', size)
                  },
                  onblur: () => {
                    draft = null
                  },
                }),
              ]
            : null,

          takes.includes('align') ? choiceField(clip, 'align', 'Text alignment', ALIGNMENTS) : null,

          takes.includes('position') ? choiceField(clip, 'position', 'Position', POSITIONS) : null,

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
