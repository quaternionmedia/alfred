import m from 'mithril'
import { Transcript } from '../captions/transcript'
import { Captions } from '../captions/store'
import { Edl } from '../Video'
import { Player } from '../Player'
import { Health } from '../Health'
import { User } from '../User'
import { SaveState } from '../Autosave'
import { JobLine, TranscribeButton, TranscribeConfirm, transcribeBlocker } from './Captions'
import { Conversation } from '../captions/conversation'
import '../captions/captions.scss'

/**
 * Transcript panel: select words (native text selection), Delete or Cut to cut them,
 * Ctrl/Cmd+Z or Undo to take a cut back. Behaviour: docs/captions.md, "Editing by text".
 */

const projectId = () => m.route.param('project')

const seconds = n => `${Number(n).toFixed(2).replace(/\.?0+$/, '')} s`
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

/** Runs of words with the same `segment`, as `{from, to}`. */
function paragraphs(words) {
  const runs = []
  words.forEach((word, i) => {
    const last = runs[runs.length - 1]
    if (last && words[last.to].segment === word.segment) last.to = i
    else runs.push({ from: i, to: i })
  })
  return runs
}

/** `[a, b]` clipped to a run, as signature text; '' if outside. */
const within = (a, b, { from, to }) =>
  a === null || b < from || a > to ? '' : `${Math.max(a, from)}-${Math.min(b, to)}`

/** Range over a word's text node (a boundary at its start is outside it). */
const textOf = element => {
  const range = document.createRange()
  range.selectNodeContents(element.firstChild || element)
  return range
}

/** Indexes `{from, to}` of the words `range` touches, or null. Binary search. */
function wordsIn(element, range) {
  const words = element.querySelectorAll('.word')
  const n = words.length
  // First word ending after the range starts.
  let lo = 0
  let hi = n
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (range.compareBoundaryPoints(Range.END_TO_START, textOf(words[mid])) < 0) hi = mid
    else lo = mid + 1
  }
  const first = lo
  // Last word starting before the range ends.
  lo = -1
  hi = n - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (range.compareBoundaryPoints(Range.START_TO_END, textOf(words[mid])) > 0) lo = mid
    else hi = mid - 1
  }
  const last = lo
  if (first >= n || last < 0 || first > last) return null
  return { from: Number(words[first].dataset.w), to: Number(words[last].dataset.w) }
}

/** Ask who said a paragraph, and name them on its words. */
const nameSpeaker = run => {
  const was = (Transcript.words[run.from] || {}).speaker || ''
  const name = window.prompt('Who said this paragraph?', was)
  if (name === null) return
  Transcript.setSpeaker(run.from, run.to, name)
}

/** One paragraph; redrawn only when its signature changes (playback redraws every frame). */
const Paragraph = {
  onbeforeupdate: (vnode, old) => vnode.attrs.signature !== old.attrs.signature,
  view: ({ attrs: { run, selection, going, current } }) => {
    const speaker = (Transcript.words[run.from] || {}).speaker || ''
    const children = [
      m(
        'button.speakerlabel',
        {
          type: 'button',
          'data-speaker': speaker,
          style: { borderColor: Conversation.colorOf(speaker) },
          title: speaker ? `Said by ${speaker}: press to change who` : 'Press to say who said this',
          onclick: e => {
            e.stopPropagation()
            nameSpeaker(run)
          },
        },
        speaker || Conversation.NOBODY
      ),
      ' ',
    ]
    for (let i = run.from; i <= run.to; i++) {
      const word = Transcript.words[i]
      const selected = selection && i >= selection.from && i <= selection.to
      if (i > run.from) children.push(' ')
      children.push(
        m(
          'span.word',
          {
            'data-w': i,
            class: [
              selected ? 'selected' : '',
              going.has(i) ? 'going' : '',
              i === current ? 'current' : '',
            ].join(' '),
            title: `${seconds(word.start)} – ${seconds(word.end)}`,
          },
          word.text
        )
      )
    }
    return m('p.transcriptpara', children)
  },
}

/** Keep the keys in the panel once the button pressed is disabled. */
const focusText = () => {
  const text = document.getElementById('transcript-text')
  if (text) text.focus({ preventScroll: true })
}

/** Cut the selection, and drop the page's text selection with it. */
const cutSelection = () => {
  if (!Transcript.cut()) return
  const selection = document.getSelection()
  if (selection) selection.removeAllRanges()
  focusText()
}

/** Undo the last cut; its words come back selected. */
const undoCut = () => {
  if (!Transcript.undo()) return
  focusText()
}

/** The words, selectable text. */
const Words = () => {
  let element = null

  // Mirrors a selection inside the words; one elsewhere (a button press) is ignored.
  const onselectionchange = () => {
    if (!element) return
    const selection = document.getSelection()
    if (!selection || !selection.rangeCount) return
    const range = selection.getRangeAt(0)
    if (range.collapsed || !range.intersectsNode(element)) return
    const held = wordsIn(element, range)
    if (held) Transcript.select(held.from, held.to)
    else Transcript.clear()
    m.redraw()
  }

  return {
    oncreate: ({ dom }) => {
      element = dom
      document.addEventListener('selectionchange', onselectionchange)
    },
    onremove: () => {
      element = null
      document.removeEventListener('selectionchange', onselectionchange)
    },
    view: () => {
      const selection = Transcript.selection
      const going = Transcript.going()
      let goingFrom = null
      let goingTo = null
      for (const i of going) {
        goingFrom = goingFrom === null ? i : Math.min(goingFrom, i)
        goingTo = goingTo === null ? i : Math.max(goingTo, i)
      }
      const current = Transcript.at(Edl.time)
      return m(
        '.transcripttext#transcript-text',
        {
          tabindex: 0,
          role: 'document',
          'aria-label': 'Transcript: select words, then press Delete to cut them from the timeline',
          // Plain click: seek to the word, drop the selection. Drag or shift-click: keep it.
          onclick: e => {
            const selection = document.getSelection()
            if (selection && !selection.isCollapsed) return
            Transcript.clear()
            const word = e.target.closest && e.target.closest('.word')
            if (word) Player.seek(Number(Transcript.words[Number(word.dataset.w)].start))
          },
          onkeydown: e => {
            if (e.key === 'Delete' || e.key === 'Backspace') {
              e.preventDefault()
              cutSelection()
            } else if (e.key === 'Escape' && Transcript.selection) {
              e.preventDefault()
              Transcript.clear()
              const selection = document.getSelection()
              if (selection) selection.removeAllRanges()
            }
          },
        },
        paragraphs(Transcript.words).map(run =>
          m(Paragraph, {
            run,
            selection,
            going,
            current,
            signature: [
              Transcript.version,
              Conversation.version,
              selection ? within(selection.from, selection.to, run) : '',
              within(goingFrom, goingTo, run),
              current >= run.from && current <= run.to ? current : '',
            ].join('|'),
          })
        )
      )
    },
  }
}

/** What the language engine reads in the words: the speakers, the topics, the tangents. */
/** The speakers named by the voices the audio engine hears, and what the last naming did. */
const NameSpeakers = {
  view: () => {
    const blocker = Transcript.cannotName()
    const last = Transcript.namedLast
    const said = last
      ? last.error
        ? `Could not name the speakers: ${last.error}`
        : `Named ${plural(last.named, 'word')} by the sound` +
          (Object.keys(last.speakers).length
            ? `: ${Object.entries(last.speakers)
                .map(([who, n]) => `${who} ${n}`)
                .join(', ')}.`
            : '.')
      : null
    return m('p.captionsnote.naming#transcript-naming', [
      m(
        'button#transcript-name-speakers',
        {
          type: 'button',
          disabled: Boolean(blocker),
          title:
            blocker ||
            'Ask the audio engine who is speaking when, and letter the words nobody has named by the voice heard over them',
          'aria-busy': Transcript.naming ? 'true' : 'false',
          onclick: () => Transcript.nameSpeakers(),
        },
        Transcript.naming ? 'Naming the speakers…' : 'Name speakers by the sound'
      ),
      said ? m('span#transcript-named', { role: 'status' }, ` ${said}`) : null,
    ])
  },
}

const Reading = {
  view: () => {
    const state = Conversation.state
    if (state === 'idle') return null
    if (state === 'no-engine') {
      return m(
        'p.captionsnote.reading#transcript-reading',
        { 'data-state': state },
        'No language engine to read who spoke and what about: set ALFRED_LANGUAGE_ENGINE_URL.'
      )
    }
    if (state === 'failed') {
      return m(
        'p.captionsnote.reading#transcript-reading',
        { 'data-state': state },
        `The language engine did not answer: ${Conversation.why || 'no reason'}`
      )
    }
    const speakers = Object.entries(Conversation.speakers)
    const topics = Conversation.topics
    const tangents = Conversation.tangents.length
    return m('.reading#transcript-reading', { 'data-state': state }, [
      m('p.captionsnote', [
        state === 'asking' ? 'Reading who spoke and what about… ' : 'Read: ',
        speakers.length
          ? speakers
              .map(([name, info]) => `${name} (${info.contributions})`)
              .join(', ')
          : 'nobody yet',
        tangents ? `; ${plural(tangents, 'tangent')}` : '',
        '.',
      ]),
      topics.length
        ? m(
            '.topics',
            topics.map(topic =>
              m(
                'button.topicchip',
                {
                  type: 'button',
                  style: { borderColor: topic.color || null },
                  title: `${topic.name}: live at ${plural(topic.points.length, 'moment')}; press to play from the first`,
                  onclick: () => {
                    if (topic.points.length) Player.seek(topic.points[0].time)
                  },
                },
                `${topic.name} ${topic.points.length}`
              )
            )
          )
        : null,
    ])
  },
}

/** Cut, Undo and Save. */
const Actions = {
  view: () => {
    const blocker = Transcript.cannotCut()
    const going = Transcript.going()
    const span = Transcript.spans()[0]
    const undo = Transcript.undoable()
    const undoTitle = undo
      ? `Put back the ${plural(undo.took.words, 'word')} the last cut took, ` +
        'and the timeline and captions with them (Ctrl+Z or Cmd+Z)'
      : Transcript.undos.length
        ? 'The timeline, the captions or the words changed since the last cut, so it stays'
        : 'Nothing to undo: a cut can be undone until something else changes'
    return m('.captionsactions', [
      m(
        'button#transcript-cut',
        {
          disabled: Boolean(blocker) || Boolean(Transcript.busy),
          title: blocker || 'Cut what these words were said in from the timeline (Delete)',
          onclick: cutSelection,
        },
        [
          m('i.material-icons', { 'aria-hidden': 'true' }, 'content_cut'),
          span ? ` Cut ${plural(going.size, 'word')}, ${seconds(span[1] - span[0])}` : ' Cut',
        ]
      ),
      m(
        'button#transcript-undo',
        {
          disabled: !undo || Boolean(Transcript.busy),
          title: undoTitle,
          onclick: undoCut,
        },
        [m('i.material-icons', { 'aria-hidden': 'true' }, 'undo'), ' Undo']
      ),
    ])
  },
}

export const TranscriptPanel = {
  oninit: () => {
    Health.watch('transcript')
    if (User.loggedIn) {
      Transcript.ensure(projectId())
      Captions.ensure(projectId())
      Conversation.follow(projectId())
    }
  },
  onupdate: () => {
    Health.catchUp()
    if (User.loggedIn) {
      Transcript.ensure(projectId())
      Captions.ensure(projectId())
      Conversation.follow(projectId())
    }
  },
  onremove: () => Health.unwatch('transcript'),
  view: () => {
    const id = projectId()
    const count = Transcript.words.length
    const last = Transcript.last
    return m('.captionspanel.transcriptpanel#panel-transcript', {
      onkeydown: e => {
        const z = e.key === 'z' || e.key === 'Z'
        if (!z || !(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey) return
        e.preventDefault()
        undoCut()
      },
    }, [
      m('.captionshead', [
        m('h3', `Transcript${count ? ` (${plural(count, 'word')})` : ''}`),
        // A cut saves itself, with the captions and words it moved (Autosave.js).
        m(SaveState, { id: 'transcript-save-state' }),
        count || Transcript.undos.length ? m(Actions) : null,
      ]),

      !id ? m('p.captionsnote', 'Choose a project on the Source stage to edit it by what is said.') : null,
      Transcript.error
        ? m('p.captionserror#transcript-error', { role: 'alert' }, Transcript.error)
        : null,

      id && Transcript.loaded && !count
        ? m('.transcriptempty', [
            // One line; the blocker, if any, says why the button waits.
            m(
              'p.captionsnote#transcript-empty',
              'No transcript yet: transcribe the timeline to edit it by what is said.' +
                (transcribeBlocker() ? ` ${transcribeBlocker()}` : '')
            ),
            m(TranscribeButton, { id: 'transcript-transcribe' }),
            m(TranscribeConfirm, { id: 'transcript-confirm' }),
          ])
        : null,
      id ? m(JobLine, { id: 'transcript-job' }) : null,

      count
        ? [
            m(NameSpeakers),
            m(
              'p.captionsnote#transcript-hint',
              Transcript.selection
                ? 'Press Delete or Backspace, or Cut, to take the struck-through words out of the timeline. Escape lets go.'
                : 'Select words — drag across them, double-click one, or click one and shift-click another — to cut them. Click a word to play from it.'
            ),
            m(Reading),
            last
              ? m(
                  'p.captionsnote#transcript-last',
                  { role: 'status' },
                  (last.undone
                    ? `Undid a cut of ${plural(last.words, 'word')}: ` +
                      `the timeline is ${seconds(last.seconds)} longer.`
                    : `Cut ${plural(last.words, 'word')}: ` +
                      `the timeline is ${seconds(last.seconds)} shorter.`) +
                    (Transcript.changed ? ' Save to keep it.' : '')
                )
              : null,
            m(Words),
          ]
        : null,
    ])
  },
}

export default TranscriptPanel
