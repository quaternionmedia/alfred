import m from 'mithril'
import './styles/tour.scss'
import { putOn } from './tourStage'

/**
 * The tour: the editor's journeys (alfred/tour.py, `GET /tour`) a stage at a
 * time, in a box over the editor. Going to a stage takes the editor there
 * (tourStage.js) and a person explores it; one word is kept on the stage,
 * under the name they give once: it works, or it is off with what is off
 * (`POST /tour/feedback`). A word is of the build it was said of: said of an
 * earlier one, it is shown as that and the stage waits again. A server that
 * keeps no words says so, and the box still tours. The box has no words of its
 * own: a stage's are the rail's, and what to try is the journey's own steps.
 *
 * The box is a popover in the browser's top layer, so no panel of the
 * workspace lays it out or covers it; it is dragged by its head and folded to
 * it by a double-click there. Where it stands, whether it is open and the
 * stage it shows are this browser's (`alfred.tour` in local storage).
 */

const KEPT = 'alfred.tour'

function kept() {
  try {
    return JSON.parse(localStorage.getItem(KEPT)) || {}
  } catch (e) {
    return {}
  }
}
function keep(more) {
  try {
    localStorage.setItem(KEPT, JSON.stringify({ ...kept(), ...more }))
  } catch (e) {
    // This browser keeps nothing.
  }
}

// A word counts for the build it was said of.
const now = s => (s.feedback && s.feedback.current ? s.feedback : null)
const mark = s =>
  s.feedback ? `${s.feedback.verdict}${s.feedback.current ? '' : ' earlier'}` : ''
const count = stages => {
  const said = stages.filter(now).length
  const off = stages.filter(s => (now(s) || {}).verdict === 'off').length
  return `${said}/${stages.length}${off ? ` · ${off} off` : ''}`
}

export const Tour = {
  journeys: [],
  stages: [],
  at: 0,
  words: true,
  busy: false,
  did: null,
  said: '',
  note: '',
  by: kept().by || '',
  box: null,

  here: () => Tour.stages[Tour.at],
  journeyOf: s => Tour.journeys[s.of],
  isOpen: () => Boolean(Tour.box && Tour.box.matches(':popover-open')),

  async read() {
    const doc = await m.request('/tour')
    const id = Tour.here() && Tour.here().id
    Tour.journeys = doc.journeys
    Tour.words = doc.words !== false
    Tour.stages = doc.journeys.flatMap((j, i) => j.stages.map(s => ({ ...s, of: i })))
    if (id) Tour.at = Math.max(0, Tour.stages.findIndex(s => s.id === id))
  },

  async put() {
    const at = Tour.here()
    if (!at || Tour.busy) return
    Tour.busy = true
    Tour.did = null
    m.redraw()
    try {
      Tour.did = await putOn(at.puts || [])
    } catch (e) {
      Tour.did = { did: [], said: `The editor did not get here: ${e.message || e}`, refused: true }
    }
    Tour.busy = false
    m.redraw()
  },

  async go(at) {
    if (at < 0 || at >= Tour.stages.length) return
    Tour.at = at
    Tour.did = null
    Tour.said = ''
    keep({ stage: Tour.here().id })
    await Tour.put()
  },

  async say(verdict) {
    const at = Tour.here()
    const by = Tour.by.trim()
    if (!by) {
      Tour.said = 'Not kept: say who you are, once, in the field below.'
      m.redraw()
      return
    }
    try {
      await m.request('/tour/feedback', {
        method: 'POST',
        body: { stage: at.id, verdict, note: Tour.note, by },
      })
    } catch (e) {
      Tour.said = `Not kept: ${(e.response && e.response.detail) || e.message}.`
      m.redraw()
      return
    }
    Tour.note = ''
    await Tour.read()
    if (Tour.at < Tour.stages.length - 1) await Tour.go(Tour.at + 1)
  },

  async open() {
    await Tour.read()
    const was = Tour.stages.findIndex(s => s.id === kept().stage)
    const first = Tour.stages.findIndex(s => !now(s))
    Tour.at = was >= 0 ? was : Math.max(0, first)
    Tour.box.showPopover()
    keep({ open: true })
    place()
    m.redraw()
  },

  close() {
    Tour.box.hidePopover()
    keep({ open: false })
  },

  toggle: () => (Tour.isOpen() ? Tour.close() : Tour.open()),
}

function place() {
  const box = Tour.box
  if (!box) return
  const { x, y } = kept()
  const w = box.offsetWidth || 352
  const h = box.offsetHeight || 200
  box.style.left = `${Math.min(Math.max(4, x == null ? 16 : x), window.innerWidth - w - 4)}px`
  box.style.top = `${Math.max(4, Math.min(y == null ? window.innerHeight - h - 48 : y, window.innerHeight - h - 8))}px`
}

function drag(e) {
  if (e.target.closest('button')) return
  const box = Tour.box
  const head = e.currentTarget
  const dx = e.clientX - box.offsetLeft
  const dy = e.clientY - box.offsetTop
  head.setPointerCapture(e.pointerId)
  const move = to => {
    keep({ x: to.clientX - dx, y: to.clientY - dy })
    place()
  }
  const up = () => {
    head.removeEventListener('pointermove', move)
    head.removeEventListener('pointerup', up)
  }
  head.addEventListener('pointermove', move)
  head.addEventListener('pointerup', up)
}

/** What the editor did to get here, what the stage needs first, and what to try. */
const More = {
  view: () => {
    const at = Tour.here()
    const needs = Tour.did && Tour.did.refused ? Tour.did.said : ''
    const done = Tour.did ? Tour.did.did : []
    if (!done.length && !needs && !at.tries.length) return null
    return m('details.tourmore', { open: Boolean(needs) || kept().more || undefined }, [
      m(
        'summary',
        { onclick: e => keep({ more: !e.currentTarget.parentNode.open }) },
        needs
          ? 'This stage needs something first'
          : [done.length && 'what the editor did', at.tries.length && `${at.tries.length} to try`]
              .filter(Boolean)
              .join(' · ')
      ),
      done.length ? m('ul.tourdid', done.map(t => m('li', t))) : null,
      needs ? m('p.tourneeds', needs) : null,
      m(
        'ul.tourtries',
        at.tries.map(t =>
          m('li', t.href ? m('a', { href: t.href, target: '_blank', rel: 'noopener' }, t.heading) : t.heading)
        )
      ),
    ])
  },
}

const Said = {
  view: () => {
    const f = Tour.here().feedback
    if (Tour.said) return m('p.tourfeedback', Tour.said)
    if (!f) return null
    return m(
      'p.tourfeedback',
      `${f.verdict === 'off' ? `✗ Off: ${f.note}` : '✓ Works'} -- said${f.by ? ` by ${f.by}` : ''} ${new Date(f.at).toLocaleString()}${
        f.current ? '' : `, of an earlier build${f.commit ? ` (${f.commit})` : ''}: this stage waits for a word again`
      }`
    )
  },
}

/** The box: rendered once per page, shown in the top layer by `Tour.open`. */
export const TourBox = {
  oncreate: ({ dom }) => {
    Tour.box = dom
    if (kept().open) Tour.open().catch(() => {})
  },
  onremove: () => {
    Tour.box = null
  },
  view: () => {
    const at = Tour.here()
    const journey = at && Tour.journeyOf(at)
    return m(
      '.tourbox#tour',
      { popover: 'manual', role: 'dialog', 'aria-label': 'Tour', class: kept().folded ? 'folded' : '' },
      at
        ? [
            m(
              'header.tourhead',
              {
                title: 'Drag to move; double-click to fold to this bar, or unfold',
                onpointerdown: drag,
                ondblclick: e => {
                  if (e.target.closest('button')) return
                  keep({ folded: !kept().folded })
                },
              },
              [
                m('span.tourtitle', `${journey.name} · ${journey.stages.indexOf(journey.stages.find(s => s.id === at.id)) + 1}. ${at.title}`),
                m('span.tourcount', { title: 'Stages with a word on this build' }, count(Tour.stages)),
                m('button.tourclose', { type: 'button', title: 'Close the tour: the editor stays as it is', onclick: () => Tour.close() }, '✕'),
              ]
            ),
            m('.tourbody', [
              m(
                'select.tourjourneys',
                {
                  'aria-label': 'Journeys',
                  value: String(at.of),
                  onchange: e => Tour.go(Tour.stages.findIndex(s => s.of === Number(e.target.value))),
                },
                Tour.journeys.map((j, i) => m('option', { value: String(i) }, `${j.name} · ${count(j.stages)}`))
              ),
              m(
                'ol.tourstages',
                journey.stages.map((s, i) =>
                  m(
                    'li',
                    m(
                      'button',
                      {
                        type: 'button',
                        class: mark(s),
                        title: s.words,
                        'aria-current': s.id === at.id ? 'step' : undefined,
                        onclick: () => Tour.go(Tour.stages.findIndex(t => t.id === s.id)),
                      },
                      `${i + 1} ${s.title}`
                    )
                  )
                )
              ),
              m('p.tourwords', [
                `${at.words}.`,
                m(
                  'button.tourput',
                  {
                    type: 'button',
                    disabled: Tour.busy,
                    title: 'Take the editor here again: chooses what this stage needs, and enters it',
                    'aria-label': 'Take the editor here',
                    onclick: () => Tour.put(),
                  },
                  '↻'
                ),
                at.tries.length && at.tries[0].href
                  ? m('a.tourpage', { href: at.tries[0].href, target: '_blank', rel: 'noopener', title: 'This journey in the user journeys, in a new tab' }, 'its journey')
                  : null,
              ]),
              m(More),
              m(Said),
              Tour.words
                ? m('label.tourwho', [
                    'as ',
                    m('input.tourby[type=text]', {
                      placeholder: 'your name',
                      'aria-label': 'Your name',
                      maxlength: 80,
                      value: Tour.by,
                      title: 'The name your words are kept under: asked once, and kept by this browser',
                      oninput: e => {
                        Tour.by = e.target.value
                        keep({ by: Tour.by.trim() })
                      },
                    }),
                  ])
                : m('p.tournowords', 'This server keeps no words on the tour.'),
              m('.tourrow', [
                m('button.tourback', { type: 'button', 'aria-label': 'Back', title: 'The stage before', disabled: Tour.at === 0, onclick: () => Tour.go(Tour.at - 1) }, '‹'),
                Tour.words
                  ? [
                      m('input.tournote[type=text]', {
                        placeholder: 'What is off',
                        'aria-label': 'What is off',
                        value: Tour.note,
                        oninput: e => (Tour.note = e.target.value),
                        onkeydown: e => e.key === 'Enter' && Tour.say('off'),
                      }),
                      m('button.tourworks', { type: 'button', title: 'This stage does what it says: kept, and on to the next', onclick: () => Tour.say('works') }, '✓ Works'),
                      m('button.touroff', { type: 'button', title: 'Something here is off, as the field says: kept, and on to the next', onclick: () => Tour.say('off') }, '✗ Off'),
                    ]
                  : null,
                m('button.tournext', { type: 'button', 'aria-label': 'Next', title: 'The next stage', disabled: Tour.at >= Tour.stages.length - 1, onclick: () => Tour.go(Tour.at + 1) }, '›'),
              ]),
            ]),
          ]
        : null
    )
  },
}

/** The way in: beside How? on the line under the rail. */
export const TourButton = {
  view: () =>
    m(
      'button.nextsteptour#tour-open',
      {
        type: 'button',
        title: "The editor's journeys a stage at a time, and your word on each",
        'aria-expanded': Tour.isOpen() ? 'true' : 'false',
        onclick: () => Tour.toggle(),
      },
      'Tour'
    ),
}

window.addEventListener('resize', () => Tour.isOpen() && place())
