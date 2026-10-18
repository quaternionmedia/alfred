import m from 'mithril'
import Sortable, { MultiDrag } from 'sortablejs'

// Sortable.mount(new MultiDrag());
var state = require("./Globals").state
import { Video, Edl, array_move } from './Video'
import { Preview } from './Preview'
import { Player } from './Player'
import { message } from 'alertifyjs'
import { auth } from './Login'
import { cutAtPlayhead } from './TimelineTools'
import { clipSeconds, roll, slide, slip, trim } from './Timing'
import { Draft } from './Draft'

// How far a press may wander and still count as a tap. Past this it is a drag
// -- on a touch screen, usually the start of scrolling the timeline -- and
// must not seek.
const TAP_SLOP = 8

/**
 * The edits a press on a clip can begin, by tool: each returns a gesture
 * (Timing.js), or `{refusal}` saying why it cannot begin there. `along` is
 * where on the clip the press landed, 0 at its start and 1 at its end.
 */
const EDITS = {
  // The clip's end follows the pointer.
  trim: ({ index }) => trim(Edl.edl[index]),
  // The clip's picture follows the pointer; its length and place do not move.
  slip: ({ index }) => slip(Edl.edl[index]),
  // The clip follows the pointer, between its neighbours.
  slide: ({ index }) => slide(Edl.edl, index),
  // The cut nearest the press follows the pointer: the one at this clip's
  // start when pressed on its first half, at its end when on its second --
  // or the only one there is, at either end of the timeline.
  'dual roller': ({ index, along }) => {
    const before = index - 1
    const after = index
    const nearest = along < 0.5 ? before : after
    const other = nearest === before ? after : before
    const exists = at => at >= 0 && at + 1 < Edl.edl.length
    return roll(Edl.edl, exists(nearest) ? nearest : other)
  },
}

// A slip changes what the viewer should show under a still playhead, so the
// picture is kept up to date while dragging rather than on release.
const FOLLOWS = new Set(['slip'])

/**
 * One clip on the timeline, and what the timeline tools do to it.
 *
 * Pointer events, not mouse events. Trim and seek listened for `mousedown`
 * and `mousemove`, which a touch screen does not send while a finger moves --
 * it sends touch events, and synthesises mouse events only after a tap -- so
 * on the phones and tablets the README promises, trimming did nothing at all.
 * Pointer events are one stream for mouse, pen and touch.
 *
 * An edit -- trim, slip, slide, roll -- captures the pointer
 * (`setPointerCapture`), so the drag keeps arriving at this clip when it
 * leaves the clip's edge -- which is most of the gesture, since the point is
 * usually to move something past it -- and the release arrives wherever it
 * happens. That replaces listeners on `document`, which had to be added and
 * removed by hand; when they were bound to the clip instead, every press
 * leaked one, and clips resized without being dragged.
 *
 * What an edit does to the clips is Timing.js's business: this turns pointer
 * movement into timeline seconds and hands them over. The clips change as the
 * pointer moves, so what the drag will leave is what is drawn while dragging,
 * and an edit the browser takes back (`pointercancel`) puts them back as they
 * were.
 *
 * Seeking happens on release, not on press. With the timeline scrollable by
 * touch, a press is as likely to be the start of a scroll as a choice of
 * position; a scroll moves the pointer (or the browser cancels it), and only a
 * press that stays put is a tap.
 */
export function Clip() {
  // The gesture in progress: an edit being dragged, or a press that may be a tap.
  let gesture = null
  // The attributes of the latest draw. This component is reused for whatever
  // clip is drawn at its position -- the list is unkeyed -- so the clip it
  // stands for, and how long that clip is, are read from the latest draw
  // rather than from the one that created it.
  let attrs = {}

  return {
    oncreate: vnode => {
      const element = vnode.dom

      const capture = id => {
        try {
          element.setPointerCapture(id)
        } catch (e) {
          // An id the browser no longer considers active. The drag still
          // works while it stays over the clip.
        }
      }

      const finishEdit = keep => {
        const { edit } = gesture
        gesture = null
        if (!keep) edit.cancel()
        // The playhead stays where it was on the timeline; what lies under it
        // may have changed, so the viewer is brought up to date.
        Player.seek(Edl.time)
      }

      element.addEventListener('pointerdown', e => {
        // The primary button, or any touch or pen contact.
        if (e.pointerType === 'mouse' && e.button !== 0) return
        if (gesture) return
        const tool = state.tool()
        const index = attrs.i
        if (EDITS[tool]) {
          if (!Edl.edl[index]) return
          const box = element.getBoundingClientRect()
          const along = box.width > 0 ? (e.clientX - box.left) / box.width : 0.5
          const edit = EDITS[tool]({ index, along })
          if (!edit || edit.refusal) {
            if (edit && edit.refusal) message(edit.refusal, 4)
            return
          }
          e.preventDefault()
          gesture = { kind: 'edit', tool, edit, id: e.pointerId, startX: e.clientX }
          capture(e.pointerId)
        } else if (tool === 'time' || tool === 'cut') {
          gesture = { kind: 'tap', tool, id: e.pointerId, x: e.clientX, y: e.clientY }
        }
      })

      element.addEventListener('pointermove', e => {
        if (!gesture || e.pointerId !== gesture.id) return
        if (gesture.kind === 'edit') {
          const scale = Number(state.scale()) || 1
          gesture.edit.apply((e.clientX - gesture.startX) / scale)
          // Keep the playhead's clip and the viewer's position honest while
          // lengths change under them; the viewer catches up on release.
          Edl.seek(Edl.time)
          if (FOLLOWS.has(gesture.tool)) Player.syncElement(true)
          m.redraw()
        } else if (
          Math.abs(e.clientX - gesture.x) > TAP_SLOP ||
          Math.abs(e.clientY - gesture.y) > TAP_SLOP
        ) {
          gesture = null
        }
      })

      element.addEventListener('pointerup', e => {
        if (!gesture || e.pointerId !== gesture.id) return
        if (gesture.kind === 'edit') return finishEdit(true)
        const tool = gesture.tool
        gesture = null
        // Where along the clip, from the clip's own box. `offsetX` is
        // relative to whichever child was under the pointer -- the name, the
        // in-point -- so pressing on the label seeked to the wrong place.
        const box = element.getBoundingClientRect()
        const along = box.width > 0 ? Math.max(0, Math.min(1, (e.clientX - box.left) / box.width)) : 0
        const at = Edl.startOf(attrs.i) + along * clipSeconds(Edl.edl[attrs.i])
        // Through the transport, so the viewer follows the click. Setting
        // `Edl.time` directly moved the playhead marker and left the
        // preview showing whatever it had been showing.
        Player.seek(at)
        // The cut tool is a razor: the playhead goes where you pressed, and
        // the clip under it splits there.
        if (tool === 'cut') cutAtPlayhead()
      })

      // The browser took the pointer back (it is scrolling, or the clip went
      // away mid-drag): an edit is abandoned rather than half-applied.
      const abandon = e => {
        if (!gesture || e.pointerId !== gesture.id) return
        if (gesture.kind === 'edit') finishEdit(false)
        else gesture = null
      }
      element.addEventListener('pointercancel', abandon)
      element.addEventListener('lostpointercapture', abandon)
    },

    onremove: () => {
      if (gesture && gesture.kind === 'edit') gesture.edit.cancel()
      gesture = null
    },

    view: vnode => {
      attrs = vnode.attrs
      const at = vnode.attrs.i
      return m(
        '.clip',
        {
          // In pixels. A bare number is an invalid length outside quirks
          // mode, so with a doctype every clip collapsed to its minimum.
          style: {
            width: `${(Number(vnode.attrs.duration) || 0) * state.scale()}px`,
          },
          ...vnode.attrs,
        },
        [
          m('i.material-icons.progress', {
            style: {
              display: Edl.current == at ? 'inherit' : 'none',
              // How far into this clip the playhead is. This used the
              // position in the source file, which counts from the file's
              // start, so on a clip that starts part-way into its file the
              // marker sat past where it should.
              left: `${Math.max(0, Edl.time - Edl.startOf(at)) * state.scale()}px`,
            },
          }),
          ...vnode.children,
        ]
      )
    },
  }
}


/** What a template clip says on the timeline: its text, else its template. */
export const templateLabel = clip => {
  const text = clip && clip.data && clip.data.text
  return text ? String(text) : (clip && clip.name) || 'template'
}

export function Template() {
  return {
    view: vnode =>
      m(
        Clip,
        {
          class: 'template',
          title: `${vnode.attrs.name}: ${templateLabel(vnode.attrs)}`,
          ...vnode.attrs,
        },
        [
          // A label, not an editor. This was a mithril-contenteditable
          // instance, and the version installed (0.1.4) renders two hard-coded
          // "<i>Hello, world</i>" divs before the editable one -- so every
          // template clip read "Hello, world Hello, world" followed by its
          // text, and editing it wrote a stale copy of the text on the next
          // keystroke. The template's settings, text included, are edited
          // beside the preview now (TemplateParams.js), where there is room to
          // show why a setting will not render.
          m('p.clipname', templateLabel(vnode.attrs)),
        ]
      ),
  }
}

/** A clip of a library file: a video, a sound, or a still picture. */
export function VideoClip() {
  return {
    view: (vnode) => {
      const still = vnode.attrs.type === 'image'
      return m(Clip, { class: vnode.attrs.type, ...vnode.attrs }, [
        m('p.clipname', String(vnode.attrs.name).split('/').pop()),
        // A still has no window onto its source to show.
        still ? null : m('p.inpoint', vnode.attrs.inpoint),
        still ? null : m('p.outpoint', vnode.attrs.outpoint),
      ])
    }
  }
}


export function OttoTimeline() {
  // Which project's clips are currently loaded, so a changed ?project= is
  // noticed. `oninit` alone was not enough: the timeline is mounted at `/`
  // now, so picking a project on the Source stage is a same-document
  // navigation that changes the parameter without remounting anything.
  // Loading only on init meant the first project opened was the only one that
  // ever appeared.
  let loaded = null
  // Which load is the latest. A project id is not enough to tell: opening A,
  // then B, then A again leaves two requests for A in flight, and both used to
  // pass the check -- the second appending A's clips after the first's.
  let ticket = 0

  const open = () => {
    // Only ask for a project when there is one to ask for. Unguarded, this
    // interpolated `undefined` into the path and requested
    // /project/undefined on every visit to the editor without a ?project=
    // parameter -- which the menu link is. The server answered 500 until it
    // was taught to answer 422; either way the request was never meaningful.
    // Normalised before the comparison, not after.
    //
    // `loaded` was set to `projectId || null` while the guard compared the raw
    // `projectId`, so with no ?project= the check was `undefined === null` --
    // false on every pass. `onupdate` runs on every redraw, so the branch
    // below re-ran continuously and cleared `Edl.edl` sixty times a second.
    //
    // The effect was that a timeline with no project selected could not be
    // built at all: a clip added from the media list, or dragged in from the
    // bin, was wiped by the next redraw before it could be seen. It looked
    // like the click had done nothing.
    const projectId = m.route.param('project') || null
    if (projectId === loaded) return
    loaded = projectId
    const mine = ++ticket

    // What is on screen belongs to the project before; anything unsaved in
    // it is kept for that project before it goes (Draft.js).
    Draft.opening()

    // Empty now, not when the response lands. The previous project's clips
    // are not this one's, and leaving them up while the request is in flight
    // made anything added meanwhile land on the wrong timeline. Not
    // `Edl.update()`: this runs inside a render (oninit, onupdate), where
    // mithril refuses a synchronous redraw.
    Edl.edl = []
    Edl.current = 0
    Edl.time = 0
    m.redraw()

    if (projectId) fetchClips(projectId, mine, 0)
  }

  const fetchClips = (projectId, mine, attempt) =>
    auth(`/project/${projectId}`, {})
      .then(e => {
        // A newer load has started since; it owns the timeline now.
        if (mine !== ticket) return
        // `e.edl` is the API's Edl document, {clips, duration}. This module's
        // `Edl.edl` is the flat clips array -- it is indexed, mapped, sliced
        // and reduced everywhere below. Assigning the document straight in
        // gave `Edl.edl.map is not a function` on every render, which is why
        // the timeline stayed empty even once projects had clips.
        //
        // Same word, two shapes. Worth remembering when reading either side.
        //
        // Anything on the timeline now was added while this request was in
        // flight, to this project, so it goes after the project's clips.
        // Assigning the response outright discarded it: choose a project,
        // add a clip before the fetch returned, and the clip vanished when it
        // did -- then Save, finding nothing on the timeline, saved nothing.
        // That was the save test failing on most runs.
        const saved = (e.edl && e.edl.clips) || []
        // What is saved is what an unsaved timeline differs from -- and a
        // timeline kept from before a reload or a new login, if it differs,
        // is offered back.
        Draft.opened(projectId, saved)
        Edl.edl = saved.concat(Edl.edl)
        Edl.current = 0
        Edl.time = 0
        Edl.update()
      })
      .catch(err => {
        if (mine !== ticket) return
        console.error('could not load the project timeline', err)
        // Try again a few times if the failure might pass, without clearing
        // anything added meanwhile.
        //
        // This used to forget the id instead, so the next redraw asked again
        // -- and every answer redraws, so a project that does not exist was
        // requested in a tight loop for as long as the page stayed open.
        // Missing (404), malformed (422) or unauthorised (401, which auth()
        // has already handled) will not change by asking again.
        const code = err && err.code
        if (code === 401 || code === 404 || code === 422 || attempt >= 3) return
        setTimeout(() => {
          if (mine === ticket) fetchClips(projectId, mine, attempt + 1)
        }, 2000 * (attempt + 1))
      })

  return {
    oninit: open,
    onupdate: () => {
      open()
      // Every change to the timeline ends in a draw of it, whatever made the
      // change -- a tool, a setting beside the viewer, a drag from the bin --
      // so this is where an unsaved timeline is kept up to date.
      Draft.observe()
    },
    // The page is leaving the editor -- to log in again, say -- so what is
    // unsaved is kept now rather than at the next throttled write.
    onremove: () => Draft.flush(),
    oncreate: (vnode) => {
      new Sortable(vnode.dom, {
        multiDrag: true,
        // Accepts drops from the bin. A bare `'clip'` accepts only its own
        // group, and the bin is `'media'`, so Sortable refused every drag
        // from the bin before the drop handler could see it.
        group: { name: 'clip', put: ['media'] },
        selectedClass: "selected",
        swapThreshold: 0.50,
        animation: 150,
        ghostClass: 'ghost',
        forceFallback: true,
        // delay: 100,
        invertSwap: true,
        preventOnFilter: false,
        filter: (e) => {
          if (state.tool() != 'move') {
            return true
          }
          else {
            return false
          }
        },
        onUpdate: (e) => {
          Edl.edl = array_move(Edl.edl, e.oldIndex, e.newIndex)
          Edl.update()
          console.log('sorting update', e, Edl.edl)
        },
        removeOnSpill: true,
        onSpill: e => {
          console.log('spilling', e)
          Edl.edl.splice(e.oldIndex, 1)
          Edl.update()
        },
      })
      window.scroll(0,0)
    },
    view: (vnode) => {
      // The tool decides the cursor and what a touch on a clip means -- a
      // scroll, or a gesture of the tool's -- so it is a class here, read by
      // editor.scss, rather than an inline cursor the toolbar used to set on
      // an element it looked up while rendering itself.
      const tool = String(state.tool()).replace(/\s+/g, '-')
      return m('#timeline.timeline', { class: `tool-${tool}` }, [
        Edl.edl.map((c, i) => {
          if (c) {
            c.i = i
            switch (c.type) {
              case 'template': return m(Template, c)
              // Stills and sounds are library clips too; they were drawn as
              // nothing at all, a gap the playhead still crossed.
              case 'video':
              case 'audio':
              case 'image': return m(VideoClip, c)
              // default: return m(Clip, c)
            }
          } else return m('')
        }),
      ])
    }
  }
}
