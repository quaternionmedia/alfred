import m from 'mithril'
import { message } from 'alertifyjs'
import { state } from '../Globals'
import { Edl } from '../Video'
import { Player } from '../Player'
import { Transcript } from '../captions/transcript'
import { Captions, captionProblem } from '../captions/store'
import { Cues } from '../cues/store'
import { Sound } from './sound'
import {
  WORD_MARK_SCALE,
  WORD_TEXT_SCALE,
  cueEnd,
  cueRow,
  dimmed,
  envelope,
  fadesOf,
  inRange,
  inView,
  placed,
  silences,
  sounding,
  tickStep,
  ticks,
  timecode,
} from './arith'
import { textCut, textEdit } from './textTools'
import './lanes.scss'

/**
 * The timeline's lanes: one time axis, several rows under it, all at the
 * editor's scale (`state.scale()`, pixels a second) in one box that scrolls
 * sideways, so what is at a second in one lane is above and below what is at
 * that second in the others. docs/lanes.md says what each lane shows.
 *
 *   Time    the ruler, labelled every so many seconds for the zoom
 *   Clips   the clips, as they always were: `#timeline`, the tools' subject
 *   Text    the transcript's words, and the captions under them
 *   Audio   the sound's loudness over each clip that plays a file, from the
 *           audio engine's analysis of the file (sound.js)
 *   FX      each clip's fades and opacity, as otto renders them
 *   Cues    what has been marked on the timeline, and where it stands
 *           (cues/store.js): the excerpts the harness proposes, for one
 *
 * The playhead is one line down all of them. A press on a lane that is not a
 * clip seeks there; a word, a caption or a cue seeks to its start. The clips
 * keep their own gestures (OttoTimeline.js). The captions and the words in
 * the Text lane are the tools' subjects too: each tool does to a caption or a
 * word what it does to a clip, as textTools.js reckons it, and what it
 * changed saves itself, as a clip's edit does.
 *
 * The lanes draw what is in view and a screen either side of it, so a long
 * recording's thousands of words cost what the screen shows; and the Text and
 * Audio lanes redraw only when something they show has changed, since
 * playback redraws the editor every frame.
 */

// How far a press may wander and still count as a tap, in pixels.
const TAP_SLOP = 8

// The tools that drag a caption or a word; Cut acts on a tap, and Time seeks.
const TEXT_DRAGS = new Set(['trim', 'move', 'slip', 'slide', 'dual roller'])

// How long a save of the captions waits for one already away, in milliseconds.
const SAVE_RETRY_MS = 400

/** The captions the lane draws, in the order they start. */
const drawnCaptions = () =>
  Captions.list
    .filter(c => !captionProblem(c))
    .sort((a, b) => Number(a.start) - Number(b.start) || Number(a.end) - Number(b.end))

/**
 * The caption or the word a press landed on: `{kind, items, index, along}`,
 * `items` the captions or the words in time order and `along` where on it the
 * press was, 0 at its start and 1 at its end; null for anything else.
 */
function textAt(e) {
  const caption = e.target.closest('.lanecaption')
  const element = caption || e.target.closest('.laneword')
  if (!element) return null
  const box = element.getBoundingClientRect()
  const along = box.width > 0 ? Math.min(1, Math.max(0, (e.clientX - box.left) / box.width)) : 1
  if (caption) {
    const items = drawnCaptions()
    const index = items.findIndex(c => String(c._key) === element.dataset.key)
    return index < 0 ? null : { kind: 'caption', items, index, along }
  }
  const index = Number(element.dataset.w)
  return Transcript.words[index] ? { kind: 'word', items: Transcript.words, index, along } : null
}

/** What a drag made of the items, into the store they came from. */
function write(edit, changes) {
  if (edit.kind === 'word') {
    const words = [...edit.items]
    changes.forEach(c => {
      words[c.index] = { ...words[c.index], start: c.start, end: c.end }
    })
    Transcript.words = words
    Transcript.version++
    return
  }
  const byKey = new Map(changes.map(c => [edit.items[c.index]._key, c]))
  Captions.replace(
    Captions.list.map(caption => {
      const change = byKey.get(caption._key)
      if (!change) return caption
      const { index, ...times } = change
      return { ...caption, ...times }
    })
  )
}

const scaleNow = () => (Number(state.scale()) > 0 ? Number(state.scale()) : 1)

const seconds = n => timecode(n, 0.1)

/** The ruler: a labelled tick every `tickStep` seconds. */
const Ruler = {
  view: ({ attrs: { px, duration, view } }) => {
    const step = tickStep(px)
    return m('.lane.ruler', [
      m('.lanelabel', 'Time'),
      ticks(duration, step, view.from, view.to).map(tick =>
        m('.tick', { style: { left: `${tick.at * px}px` } }, tick.label)
      ),
    ])
  },
}

/** The transcript's words, and the captions under them. */
function TextLane() {
  return {
    onbeforeupdate: (vnode, old) => vnode.attrs.signature !== old.attrs.signature,
    view: ({ attrs: { px, view } }) => {
      const words = Transcript.words
      const current = Transcript.at(Edl.time)
      const selection = Transcript.selection
      const going = Transcript.going()
      const items = []
      if (px >= WORD_MARK_SCALE) {
        words.forEach((word, i) => {
          const start = Number(word.start)
          const end = Number(word.end)
          if (!inRange(start, end, view)) return
          items.push(
            m(
              'span.laneword',
              {
                'data-w': i,
                'data-seek': '',
                class: [
                  px < WORD_TEXT_SCALE ? 'mark' : '',
                  i === current ? 'current' : '',
                  selection && i >= selection.from && i <= selection.to ? 'selected' : '',
                  going.has(i) ? 'going' : '',
                ].join(' '),
                style: { left: `${start * px}px`, width: `${Math.max(2, (end - start) * px)}px` },
                title: `${word.text} · ${seconds(start)}–${seconds(end)}`,
                onclick: () => Player.seek(start),
              },
              px >= WORD_TEXT_SCALE ? word.text : null
            )
          )
        })
      }
      Captions.list.forEach(caption => {
        if (captionProblem(caption)) return
        const start = Number(caption.start)
        const end = Number(caption.end)
        if (!inRange(start, end, view)) return
        items.push(
          m(
            '.lanecaption',
            {
              'data-seek': '',
              'data-key': caption._key,
              'data-start': start,
              class: start <= Edl.time && Edl.time < end ? 'on' : '',
              style: { left: `${start * px}px`, width: `${Math.max(2, (end - start) * px)}px` },
              title: `${caption.text} · ${seconds(start)}–${seconds(end)}`,
            },
            caption.text
          )
        )
      })
      const label = words.length
        ? 'Text'
        : Transcript.loading
          ? 'Text · loading…'
          : Captions.list.length
            ? 'Text · captions'
            : 'Text · no transcript'
      return m('.lane.text', [m('.lanelabel', label), items])
    },
  }
}

/** What the lane's label adds about the files' analyses. */
function soundNote(states) {
  if (states.has('asking')) return ' · hearing…'
  if (states.has('no-engine')) return ' · no audio engine'
  if (states.has('failed')) return ' · not analysed'
  return ''
}

/** The sound's loudness over each clip that plays a file. */
function AudioLane() {
  return {
    onbeforeupdate: (vnode, old) => vnode.attrs.signature !== old.attrs.signature,
    view: ({ attrs: { px } }) => {
      const clips = placed(Edl.edl)
      const duration = clips.reduce((end, at) => Math.max(end, at.start + at.length), 0)
      const drawn = []
      const quiet = []
      const states = new Set()
      clips.forEach(at => {
        if (!sounding(at.clip)) return
        const sound = Sound.of(at.clip.name)
        states.add(sound.state)
        if (sound.state !== 'heard') return
        const points = envelope(at, sound.peaks, px)
        if (points) drawn.push(m('polygon.envelope', { points }))
        silences(at, sound.silences).forEach(s =>
          quiet.push(m('rect.silence', { x: s.start, y: 0, width: s.end - s.start, height: 1 }))
        )
      })
      return m('.lane.audio', [
        m('.lanelabel', `Audio${soundNote(states)}`),
        duration > 0
          ? m(
              'svg',
              {
                width: `${duration * px}px`,
                viewBox: `0 0 ${duration} 1`,
                preserveAspectRatio: 'none',
              },
              [...quiet, ...drawn]
            )
          : null,
      ])
    },
  }
}

/** Each clip's fades and opacity, as otto renders them. */
const FxLane = {
  view: ({ attrs: { px, view } }) => {
    const items = []
    placed(Edl.edl).forEach(at => {
      if (!inRange(at.start, at.start + at.length, view)) return
      const fades = fadesOf(at.clip)
      if (fades.in > 0) {
        const length = Math.min(fades.in, at.length)
        items.push(
          m('.fade.in', {
            style: { left: `${at.start * px}px`, width: `${length * px}px` },
            title: `Fade in, ${fades.in} s`,
          })
        )
      }
      if (fades.out > 0) {
        const length = Math.min(fades.out, at.length)
        items.push(
          m('.fade.out', {
            style: { left: `${(at.start + at.length - length) * px}px`, width: `${length * px}px` },
            title: `Fade out, ${fades.out} s`,
          })
        )
      }
      const opacity = dimmed(at.clip)
      if (opacity !== null) {
        items.push(
          m(
            '.dim',
            {
              style: { left: `${at.start * px}px`, width: `${at.length * px}px` },
              title: `Opacity ${opacity}`,
            },
            `${Math.round(opacity * 100)}%`
          )
        )
      }
    })
    return m('.lane.fx', [m('.lanelabel', 'FX'), items])
  },
}

/** What a cue says when pointed at. */
function cueTitle(cue, start, end) {
  const where = end > start ? `${seconds(start)}–${seconds(end)}` : seconds(start)
  const lines = [`${cue.label} · ${where}${cue.state ? ` · ${cue.state}` : ''}`]
  if (cue.note) lines.push(cue.note)
  return lines.join('\n')
}

/** What has been marked on the timeline, and where it stands. */
const CuesLane = {
  view: ({ attrs: { px, view } }) => {
    const t = Edl.time
    const items = []
    Cues.list.forEach(cue => {
      const start = Number(cue.start) || 0
      const end = cueEnd(cue)
      if (!inRange(start, end, view)) return
      const point = end <= start
      items.push(
        m(
          '.cue',
          {
            'data-seek': '',
            class: [
              cue.kind || '',
              cue.state || '',
              point ? 'point' : '',
              cueRow(cue) ? 'below' : '',
              start <= t && t <= end ? 'on' : '',
            ].join(' '),
            style: { left: `${start * px}px`, width: point ? null : `${Math.max(2, (end - start) * px)}px` },
            title: cueTitle(cue, start, end),
            onclick: () => Player.seek(start),
          },
          point ? null : cue.label
        )
      )
    })
    const label = Cues.error ? 'Cues · not loaded' : 'Cues'
    return m('.lane.cues', [m('.lanelabel', label), items])
  },
}

/** What the Text lane shows, in a string: it redraws when this changes. */
function textSignature(px, view, captionsVersion) {
  const selection = Transcript.selection
  const t = Edl.time
  const caption = Captions.list.findIndex(
    c => !captionProblem(c) && Number(c.start) <= t && t < Number(c.end)
  )
  return [
    Transcript.version,
    captionsVersion,
    px,
    view.from.toFixed(1),
    view.to.toFixed(1),
    Transcript.at(t),
    selection ? `${selection.from}-${selection.to}` : '',
    caption,
  ].join('|')
}

/** What the Audio lane shows, in a string. */
function audioSignature(px) {
  const parts = placed(Edl.edl)
    .filter(at => sounding(at.clip))
    .map(at => {
      const known = Sound.byName.get(at.clip.name)
      return `${at.clip.name}@${at.start}+${at.length}<${at.inpoint}:${known ? known.state : ''}`
    })
  return `${px}|${parts.join(',')}`
}

export function Lanes() {
  let dom = null
  // The scroll box's position and width, in pixels, read when it scrolls or resizes.
  let box = { left: 0, width: 0 }
  let press = null
  let frame = null
  let observer = null
  // Bumped when the captions list is another array: it is replaced on every change.
  let captionsSeen = null
  let captionsVersion = 0

  const measure = () => {
    if (!dom) return false
    const left = dom.scrollLeft
    const width = dom.clientWidth
    if (left === box.left && width === box.width) return false
    box = { left, width }
    return true
  }

  const onscroll = () => {
    if (frame) return
    frame = requestAnimationFrame(() => {
      frame = null
      if (measure()) m.redraw()
    })
  }

  /** Put the playhead at the pointer's second. */
  const seekAt = clientX => {
    const body = dom && dom.querySelector('.lanebody')
    if (!body) return
    const x = clientX - body.getBoundingClientRect().left
    Player.seek(Math.max(0, x / scaleNow()))
  }

  // A save asked for while another was away: whether it carries the words.
  let wanted = null
  let retry = null

  /**
   * The captions as they stand, and the words when `words`, saved: an edit
   * in the lane saves itself as a clip's does, and one that lands while a
   * save is away is saved after it. A caption the Captions panel holds
   * incomplete stops this; that panel's Save keeps the change once it is
   * whole.
   */
  const saveText = words => {
    wanted = { words: Boolean(words || (wanted && wanted.words)) }
    if (Captions.busy) {
      clearTimeout(retry)
      retry = setTimeout(() => saveText(false), SAVE_RETRY_MS)
      return
    }
    if (!Captions.canSave()) return
    const asked = wanted
    wanted = null
    Captions.save(asked.words ? { words: Transcript.wordsToSave() } : {}).then(saved => {
      if (saved && asked.words) Transcript.saved()
      if (wanted) saveText(false)
    })
  }

  /** A drag in the Text lane, abandoned: what it moved is put back. */
  const undoDrag = drag => {
    if (drag.kind === 'word') {
      Transcript.words = drag.items
      Transcript.version++
    } else write(drag, drag.gesture.apply(0))
  }

  /** A drag in the Text lane is done: the list settled and saved. */
  const finishDrag = drag => {
    if (drag.kind === 'word') {
      Transcript.changed = true
      saveText(true)
      return
    }
    Captions.commit()
    saveText(false)
  }

  /** A tap with the Cut tool on a caption: it splits there, or says why not. */
  const cutText = found => {
    const item = found.items[found.index]
    const at = Number(item.start) + found.along * (Number(item.end) - Number(item.start))
    const halves = textCut(found.kind, item, at, Transcript.words)
    if (halves.refusal) {
      message(halves.refusal, 4)
      return
    }
    const { _key, ...second } = halves.second
    Captions.replace(
      Captions.list.flatMap(c => (c._key === item._key ? [halves.first, second] : [c]))
    )
    Captions.sort()
    saveText(false)
    Player.seek(Number(halves.second.start))
  }

  return {
    oncreate: ({ dom: element }) => {
      dom = element
      element.addEventListener('scroll', onscroll, { passive: true })
      if (typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(() => {
          if (measure()) m.redraw()
        })
        observer.observe(element)
      }
      if (measure()) m.redraw()
    },

    onremove: () => {
      if (observer) observer.disconnect()
      if (frame) cancelAnimationFrame(frame)
      clearTimeout(retry)
      dom = null
    },

    // Playing, the lanes keep the playhead in view.
    onupdate: () => {
      if (!dom || !Player.playing) return
      const x = Edl.time * scaleNow()
      if (x < dom.scrollLeft || x > dom.scrollLeft + dom.clientWidth - 24) {
        dom.scrollLeft = Math.max(0, x - dom.clientWidth * 0.2)
      }
    },

    view: ({ children }) => {
      const px = scaleNow()
      const duration = Edl.duration()
      const view = inView(box.left, box.width || 1200, px)
      if (Captions.list !== captionsSeen) {
        captionsSeen = Captions.list
        captionsVersion++
      }
      const tool = String(state.tool()).replace(/\s+/g, '-')
      return m(
        '.lanes',
        { class: `tool-${tool}` },
        m(
          '.lanebody',
          {
            style: { width: `${Math.max(1, duration * px)}px` },
            onpointerdown: e => {
              if (e.pointerType === 'mouse' && e.button !== 0) return
              if (e.target.closest('#timeline')) return
              press = { id: e.pointerId, x: e.clientX, y: e.clientY }
              const tool = state.tool()
              if (tool !== 'cut' && !TEXT_DRAGS.has(tool)) return
              const found = textAt(e)
              if (!found) return
              if (tool === 'cut') {
                press.cut = found
                return
              }
              const gesture = textEdit(tool, found.kind, found.items, found.index, found.along, Transcript.words)
              if (!gesture) return
              if (gesture.refusal) {
                message(gesture.refusal, 4)
                return
              }
              // What the tool moves follows the pointer until the release,
              // wherever that happens: the pointer is captured, as a clip's
              // edits capture it (OttoTimeline.js).
              press.drag = { ...found, gesture, moved: false }
              e.preventDefault()
              try {
                e.currentTarget.setPointerCapture(e.pointerId)
              } catch (err) {
                // An id the browser no longer considers active: the drag
                // still works while it stays over the lanes.
              }
            },
            onpointermove: e => {
              if (!press || !press.drag || e.pointerId !== press.id) return
              const drag = press.drag
              drag.moved = drag.moved || Math.abs(e.clientX - press.x) > TAP_SLOP
              if (!drag.moved) return
              write(drag, drag.gesture.apply((e.clientX - press.x) / scaleNow()))
              m.redraw()
            },
            onpointerup: e => {
              if (!press || e.pointerId !== press.id) return
              const wandered =
                Math.abs(e.clientX - press.x) > TAP_SLOP || Math.abs(e.clientY - press.y) > TAP_SLOP
              const { drag, cut } = press
              press = null
              if (drag && drag.moved) return finishDrag(drag)
              if (cut) {
                if (!wandered) cutText(cut)
                return
              }
              if (drag) {
                // A press that stayed put is a tap, whatever the tool: it
                // seeks to the start of what was pressed, as the release's
                // target is the lanes, which hold the pointer.
                undoDrag(drag)
                if (!wandered) Player.seek(Number(drag.items[drag.index].start) || 0)
                return
              }
              const caption = e.target.closest('.lanecaption')
              if (caption) {
                if (!wandered) Player.seek(Number(caption.dataset.start) || 0)
                return
              }
              // A clip, a word and a cue each seek for themselves.
              if (wandered || e.target.closest('#timeline') || e.target.closest('[data-seek]')) return
              seekAt(e.clientX)
            },
            // The browser took the pointer back (it is scrolling), or the
            // capture went with a release already settled: a drag half done
            // is put back rather than half applied.
            onpointercancel: e => {
              if (press && press.drag && e.pointerId === press.id) undoDrag(press.drag)
              press = null
            },
            onlostpointercapture: e => {
              if (!press || !press.drag || e.pointerId !== press.id) return
              undoDrag(press.drag)
              press = null
            },
          },
          [
            m(Ruler, { px, duration, view }),
            m('.lane.clips', [m('.lanelabel', 'Clips'), children]),
            m(TextLane, { px, view, signature: textSignature(px, view, captionsVersion) }),
            m(AudioLane, { px, signature: audioSignature(px) }),
            m(FxLane, { px, view }),
            m(CuesLane, { px, view }),
            m('.playhead', { style: { left: `${Edl.time * px}px` } }),
          ]
        )
      )
    },
  }
}

export default Lanes
