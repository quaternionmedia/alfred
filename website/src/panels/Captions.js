import m from 'mithril'
import { Captions, DRAWN, captionProblem } from '../captions/store'
import { Edl } from '../Video'
import { Player } from '../Player'
import { Health } from '../Health'
import { User } from '../User'
import '../captions/captions.scss'

/**
 * The Captions panel (contract K3): a project's captions and how they are
 * drawn.
 *
 * Edit them by hand -- start, end, text; add at the playhead, delete -- or
 * import a subtitle file (SubRip, WebVTT or JSON), which the server reads and
 * this shows for review before it saves; or have the timeline's own sound
 * transcribed by the server's audio engine. The style says how the captions
 * are drawn into renders, and whether they are.
 *
 * A panel assumes nothing about where it sits: it fills its container and
 * scrolls inside it, and it reads the project from the route, as every stage
 * does. What it edits is the page's caption store (`captions/store.js`), which
 * the viewer's overlay and the render request read too.
 */

const projectId = () => m.route.param('project')

/** Why transcribing cannot be asked for now, or '' when it can. */
export function transcribeBlocker() {
  if (!projectId()) return 'Choose a project first.'
  const engine = Health.state && Health.state.audio_engine
  if (engine && !engine.configured) {
    return 'No audio engine is configured on the server (ALFRED_AUDIO_ENGINE_URL).'
  }
  if (engine && !engine.ok) {
    return `The audio engine cannot be reached: ${engine.detail || 'it did not answer'}`
  }
  if (Health.rendererDown()) return "No renderer is running to mix the timeline's sound."
  return ''
}

const JOB_SAYS = {
  queued: () => 'Queued: the timeline is waiting to be transcribed…',
  transcribing: () => 'Transcribing the timeline…',
  done: job =>
    `Transcribed: ${job.segments ?? 0} segment${job.segments === 1 ? '' : 's'} of speech heard` +
    (job.engine ? ` by ${job.engine}` : '') +
    '.',
  failed: job => `Transcription failed: ${job.error || 'no reason was given'}`,
}

const JobLine = {
  view: () => {
    const job = Captions.job
    if (!job || !JOB_SAYS[job.state]) return null
    return m(
      'p.captionsjob#captions-job',
      { class: job.state, 'data-state': job.state, role: 'status' },
      JOB_SAYS[job.state](job)
    )
  },
}

/** A file picker behind a button: the input itself is hidden. */
const ImportButton = () => {
  let input = null
  return {
    view: () => [
      m('input#captions-file', {
        type: 'file',
        accept: '.srt,.vtt,.json,.txt,text/vtt,application/json',
        hidden: true,
        oncreate: vnode => {
          input = vnode.dom
        },
        onchange: e => {
          const [file] = e.target.files || []
          if (file) Captions.importFile(file)
          // The same file again is a change too.
          e.target.value = ''
        },
      }),
      m(
        'button#captions-import',
        {
          disabled: !Captions.loaded || Boolean(Captions.busy),
          title: 'Read captions from a SubRip (.srt), WebVTT (.vtt) or JSON file',
          onclick: () => input && input.click(),
        },
        Captions.busy === 'import' ? 'Reading…' : 'Import…'
      ),
    ],
  }
}

const Review = {
  view: () => {
    const review = Captions.review
    if (!review) return null
    const count = review.captions.length
    return m('.captionsreview#captions-review', [
      m(
        'p',
        `${review.name}: ${count} caption${count === 1 ? '' : 's'}` +
          (review.skipped ? `, ${review.skipped} left out for having no text or no length` : '') +
          '.'
      ),
      count
        ? m(
            'ol',
            review.captions
              .slice(0, 5)
              .map(c => m('li', `${c.start.toFixed(3)}–${c.end.toFixed(3)} ${c.text}`))
              .concat(count > 5 ? [m('li', '…')] : [])
          )
        : null,
      m('.confirm', [
        m(
          'button.primary#captions-review-replace',
          { disabled: !count || Boolean(Captions.busy), onclick: () => Captions.acceptReview('replace') },
          Captions.list.length ? 'Replace and save' : 'Use and save'
        ),
        Captions.list.length
          ? m(
              'button#captions-review-append',
              { disabled: !count || Boolean(Captions.busy), onclick: () => Captions.acceptReview('append') },
              'Add to these and save'
            )
          : null,
        m('button#captions-review-cancel', { onclick: Captions.dismissReview }, 'Cancel'),
      ]),
    ])
  },
}

const POSITIONS = [
  ['bottom', 'Bottom'],
  ['top', 'Top'],
  ['center', 'Middle'],
]
const ALIGNMENTS = [
  ['center', 'Centred'],
  ['west', 'Left'],
  ['east', 'Right'],
]
const FONTS = ['DejaVu-Sans', 'DejaVu-Sans-Bold', 'DejaVu-Serif', 'DejaVu-Sans-Mono']

const positionValue = position => (Array.isArray(position) ? position.join(',') : position)

const StyleControls = {
  view: () => {
    const style = Captions.style
    const off = !Captions.loaded
    const boxed = style.bg !== ''
    return m('.captionsstyle#captions-style', [
      m('label.inline', [
        m('input#caption-enabled', {
          type: 'checkbox',
          disabled: off,
          checked: style.enabled === true,
          onchange: e => Captions.setStyle({ enabled: e.target.checked }),
        }),
        'Draw into renders',
      ]),
      m('label', [
        'Size',
        m('input#caption-size', {
          type: 'number',
          min: 8,
          max: 200,
          step: 1,
          disabled: off,
          placeholder: String(DRAWN.fontsize),
          title: 'Pixels in a 1080-line frame; scaled with the render',
          value: style.fontsize ?? '',
          oninput: e => {
            const size = parseInt(e.target.value, 10)
            Captions.setStyle({ fontsize: Number.isFinite(size) ? size : null })
          },
        }),
      ]),
      m('label', [
        'Position',
        m(
          'select#caption-position',
          {
            disabled: off,
            value: positionValue(style.position || DRAWN.position),
            onchange: e => Captions.setStyle({ position: e.target.value }),
          },
          POSITIONS.map(([value, label]) => m('option', { value }, label))
        ),
      ]),
      m('label', [
        'Lines',
        m(
          'select#caption-align',
          {
            disabled: off,
            value: style.align || DRAWN.align,
            onchange: e => Captions.setStyle({ align: e.target.value }),
          },
          ALIGNMENTS.map(([value, label]) => m('option', { value }, label))
        ),
      ]),
      m('label', [
        'Text',
        m('input#caption-color', {
          type: 'color',
          disabled: off,
          value: style.color || DRAWN.color,
          oninput: e => Captions.setStyle({ color: e.target.value }),
        }),
      ]),
      m('label.inline', [
        m('input#caption-box', {
          type: 'checkbox',
          disabled: off,
          checked: boxed,
          onchange: e => Captions.setStyle({ bg: e.target.checked ? null : '' }),
        }),
        'Box',
      ]),
      boxed
        ? m('label', [
            'Box colour',
            m('input#caption-bg', {
              type: 'color',
              disabled: off,
              value: style.bg || DRAWN.bg,
              oninput: e => Captions.setStyle({ bg: e.target.value }),
            }),
          ])
        : null,
      m('label', [
        'Font',
        m(
          'select#caption-font',
          {
            disabled: off,
            value: style.font || DRAWN.font,
            onchange: e => Captions.setStyle({ font: e.target.value }),
          },
          FONTS.map(font => m('option', { value: font }, font.replace(/-/g, ' ')))
        ),
      ]),
    ])
  },
}

const TimeField = {
  view: ({ attrs: { caption, field, label } }) =>
    m(`input.caption-${field}`, {
      type: 'number',
      min: 0,
      step: 0.1,
      'aria-label': `${label} (seconds)`,
      title: `${label}, in seconds of the timeline`,
      value: caption[field],
      oninput: e => Captions.update(caption._key, field, e.target.value),
      onchange: () => Captions.commit(),
    }),
}

const Row = {
  view: ({ attrs: { caption, number } }) => {
    const problem = captionProblem(caption)
    const now = Edl.time
    const current = !problem && Number(caption.start) <= now && now < Number(caption.end)
    return m(
      'li.captionrow',
      { class: [problem ? 'invalid' : '', current ? 'current' : ''].join(' ') },
      [
        m('.captiontime', [
          m(
            'button.icon.caption-seek',
            {
              title: 'Play from here',
              'aria-label': `Play caption ${number} from its start`,
              onclick: () => Player.seek(Number(caption.start) || 0),
            },
            m('i.material-icons', 'play_arrow')
          ),
          m(TimeField, { caption, field: 'start', label: 'Start' }),
          m(
            'button.icon.caption-start-here',
            {
              title: 'Start at the playhead',
              'aria-label': `Start caption ${number} at the playhead`,
              onclick: () => {
                Captions.update(caption._key, 'start', Edl.time)
                Captions.commit()
              },
            },
            m('i.material-icons', 'first_page')
          ),
        ]),
        m('.captiontime', [
          m(TimeField, { caption, field: 'end', label: 'End' }),
          m(
            'button.icon.caption-end-here',
            {
              title: 'End at the playhead',
              'aria-label': `End caption ${number} at the playhead`,
              onclick: () => {
                Captions.update(caption._key, 'end', Edl.time)
                Captions.commit()
              },
            },
            m('i.material-icons', 'last_page')
          ),
        ]),
        m('textarea.caption-text', {
          rows: 1,
          maxlength: 500,
          'aria-label': `Caption ${number} text`,
          placeholder: 'What is said',
          value: caption.text,
          oninput: e => Captions.update(caption._key, 'text', e.target.value),
        }),
        m(
          'button.icon.caption-delete',
          {
            title: 'Delete this caption',
            'aria-label': `Delete caption ${number}`,
            onclick: () => Captions.remove(caption._key),
          },
          m('i.material-icons', 'delete')
        ),
        problem ? m('span.captionproblem', problem) : null,
      ]
    )
  },
}

const TranscribeButton = {
  view: () => {
    const blocker = transcribeBlocker()
    const running = Captions.running() || Captions.busy === 'transcribe'
    return m(
      'button#captions-transcribe',
      {
        disabled: Boolean(blocker) || running || !Captions.loaded || Boolean(Captions.busy),
        title: blocker || "Hear the saved timeline's sound and caption what it says",
        'aria-busy': running ? 'true' : 'false',
        onclick: () => {
          if (Captions.list.length) Captions.confirming = true
          else Captions.transcribe()
        },
      },
      running ? 'Transcribing…' : 'Transcribe timeline'
    )
  },
}

export const CaptionsPanel = {
  oninit: () => {
    Health.watch('captions')
    if (User.loggedIn) Captions.ensure(projectId())
  },
  onupdate: () => {
    Health.catchUp()
    if (User.loggedIn) Captions.ensure(projectId())
  },
  onremove: () => Health.unwatch('captions'),
  view: () => {
    const id = projectId()
    const count = Captions.list.length
    const blocker = transcribeBlocker()
    const problems = Captions.problems().filter(Boolean).length
    return m('.captionspanel#panel-captions', [
      m('.captionshead', [
        m('h3', `Captions${count ? ` (${count})` : ''}`),
        Captions.dirty() ? m('span.captionsnote#captions-unsaved', 'Unsaved changes') : null,
        m('.captionsactions', [
          m(
            'button#caption-add',
            {
              disabled: !Captions.loaded,
              title: 'Add a caption at the playhead',
              onclick: () => Captions.add(Edl.time),
            },
            'Add at playhead'
          ),
          m(ImportButton),
          m(TranscribeButton),
          m(
            'button.primary#captions-save',
            {
              disabled: !Captions.canSave() || !Captions.dirty(),
              title: problems
                ? 'Fix the captions marked in red first'
                : 'Save the captions and their style to the project',
              onclick: () => Captions.save(),
            },
            Captions.busy === 'save' ? 'Saving…' : 'Save'
          ),
        ]),
      ]),

      !id ? m('p.captionsnote', 'Choose a project on the Source stage to caption it.') : null,
      id && blocker ? m('p.captionsnote#captions-transcribe-reason', blocker) : null,
      id && !blocker
        ? m(
            'p.captionsnote',
            "Transcribing hears the project's saved timeline and replaces these captions."
          )
        : null,

      Captions.confirming
        ? m('.confirm#captions-confirm', [
            m('span', `Replace the ${count} caption${count === 1 ? '' : 's'} with what the timeline says?`),
            m('button.primary#captions-confirm-yes', { onclick: () => Captions.transcribe() }, 'Replace'),
            m(
              'button#captions-confirm-no',
              { onclick: () => (Captions.confirming = false) },
              'Cancel'
            ),
          ])
        : null,
      m(JobLine),
      Captions.error ? m('p.captionserror#captions-error', { role: 'alert' }, Captions.error) : null,
      m(Review),

      m(StyleControls),

      count
        ? m(
            'ol.captionlist#captions-list',
            Captions.list.map((caption, i) =>
              m(Row, { key: caption._key, caption, number: i + 1 })
            )
          )
        : id && Captions.loaded
          ? m(
              'p.captionsnote#captions-empty',
              'No captions yet. Add one at the playhead, import a subtitle file, or transcribe the timeline.'
            )
          : null,
    ])
  },
}

export default CaptionsPanel
