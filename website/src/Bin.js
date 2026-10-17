import m from 'mithril'
import { Sortable } from 'sortablejs'
import { auth } from './Login'
import { User } from './User'
import { addClip, templateClip, videoClip } from './Clips'

/**
 * The media bin: every template and media file, to drag onto the timeline or
 * add with a click.
 *
 * Neither worked for templates. The timeline's Sortable group refused drops
 * from the bin's group outright, so a drag never landed; and the drop handler
 * read `type` and `datastr` back out of the dragged element's attributes,
 * which `/templates` entries do not have -- `GET /templates` describes
 * templates (name, description, parameters), not clips -- so it threw on
 * `clip.type.value` when one did. Template clips only ever reached a timeline
 * through demo and seed projects.
 *
 * Entries now carry only which item they are; the clip is built from the
 * bin's own data by the same functions the Source stage uses (Clips.js). And
 * each entry has an add button, so adding does not depend on a drag -- which
 * is no use from a keyboard and awkward on a phone.
 */

var Bin = {
  videos: [],
  templates: [],
  loaded: false,

  // Fetch once a session exists, and not before.
  //
  // Two reasons this is not just `oninit`. The timeline is mounted at `/` now,
  // so an anonymous visitor lands on it -- and these calls each answered 401
  // and each raised an alertify "not authorized" toast, so the login page
  // arrived wearing two error notices it had not earned. And a restored
  // session resolves asynchronously, so `oninit` can run before `loggedIn` is
  // true; loading only there left the bin permanently empty for anyone who
  // arrived by reload rather than by logging in.
  fill: () => {
    if (Bin.loaded || !User.loggedIn) return
    Bin.loaded = true

    // `m.request` here, not `auth`, meant no Authorization header on a route
    // that requires one -- so /videos answered 401 every time and the media
    // bin was permanently empty. Nothing surfaced it: the rejection was never
    // handled, so the bin simply rendered nothing.
    auth('/videos')
      .then(e => {
        Bin.videos = e
        m.redraw()
      })
      .catch(e => {
        Bin.loaded = false
        console.error('could not load videos for the bin', e)
      })

    auth('/templates')
      .then(e => {
        Bin.templates = e
        m.redraw()
      })
      .catch(e => {
        Bin.loaded = false
        console.error('could not load templates for the bin', e)
      })
  },

  /** The clip a bin entry stands for, built fresh. */
  clipFor: (kind, name) => {
    if (kind === 'template') {
      return templateClip(Bin.templates.find(t => t.name === name) || name)
    }
    if (kind === 'video') return videoClip(name)
    return null
  },

  oninit: () => Bin.fill(),
  onupdate: () => Bin.fill(),
  oncreate: vnode => {
    new Sortable(vnode.dom, {
      group: {
        name: 'media',
        pull: 'clone',
        put: false,
      },
      sort: false,
      // The add buttons are buttons, not drag handles.
      filter: '.binadd',
      preventOnFilter: false,
      ghostClass: 'ghost',
      forceFallback: true,
      animation: 150,
      onEnd: e => {
        if (!e.to || e.to.id !== 'timeline') return
        // Undo Sortable's move before anything else. Pulling a clone moves the
        // dragged element into the timeline and leaves a copy in its place --
        // a copy mithril did not make, with none of its event handlers, so
        // that entry's add button stopped working after one drag. Swapping
        // them back leaves both lists exactly as mithril drew them; the
        // timeline then redraws with the new clip from Edl.
        if (e.clone && e.clone.parentNode) {
          e.clone.parentNode.replaceChild(e.item, e.clone)
        } else if (e.item.parentNode) {
          e.item.parentNode.removeChild(e.item)
        }
        const clip = Bin.clipFor(e.item.dataset.binKind, e.item.dataset.binName)
        if (clip) addClip(clip, e.newIndex)
      },
    })
  },

  view: () =>
    m('#bin.bin.project', [
      Bin.templates.map(t =>
        m(BinEntry, {
          key: `template:${t.name}`,
          kind: 'template',
          name: t.name,
          label: t.name,
          title: t.description ? t.description.replace(/\*/g, '') : t.name,
        })
      ),
      Bin.videos.map(f =>
        m(BinEntry, {
          key: `video:${f}`,
          kind: 'video',
          name: f,
          label: String(f).split('/').pop(),
          title: f,
        })
      ),
    ]),
}

/**
 * One entry. Styled as a clip, so it reads as the thing it becomes -- but not
 * a timeline `Clip`: those carry the trim and seek handlers, which on a bin
 * entry resized the entry or seeked to a clip that does not exist.
 */
const BinEntry = {
  view: ({ attrs }) =>
    m(
      '.clip.binclip',
      {
        class: attrs.kind === 'template' ? 'template' : 'video',
        name: attrs.name,
        title: attrs.title,
        'data-bin-kind': attrs.kind,
        'data-bin-name': attrs.name,
      },
      [
        m('span.binlabel', attrs.label),
        m(
          'button.binadd',
          {
            type: 'button',
            title: `Add ${attrs.label} to the timeline`,
            'aria-label': `Add ${attrs.label} to the timeline`,
            onclick: () => {
              const clip = Bin.clipFor(attrs.kind, attrs.name)
              if (clip) addClip(clip)
            },
          },
          m('i.material-icons', 'add')
        ),
      ]
    ),
}

export default Bin
