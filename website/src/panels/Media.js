import m from 'mithril'
import { auth } from '../Login'
import Bin, { seconds } from '../Bin'
import { Library } from '../Library'
import { Flow, FlowPanel, Generate, addMedia, addTemplate, basename } from '../Stages'

/**
 * Media & templates: everything that can go on the timeline, as a panel.
 *
 * The second half of what the Source stage showed -- the files on the server
 * and the templates a clip can be made from, each a button that puts one on
 * the end of the timeline and says where it landed. The bin under the
 * timeline lists the same things to drag (Bin.js); this is the list that can
 * be read, with lengths, and that offers to generate media on an empty
 * install.
 *
 * The templates are the bin's: it fetches them. Asked for here as well, so
 * the panel lists them wherever it sits, whether or not a bin is on screen.
 */
const MediaPanel = {
  oninit: () => Bin.fill(),
  onupdate: () => Bin.fill(),
  view: () =>
    m('.stagepanel#panel-media', [
      m('h3', `Material${Library.items.length ? ` (${Library.items.length})` : ''}`),
      Library.items.length
        ? [
            m(
              'p.stagehint',
              'Choose a clip to put it on the timeline.'
            ),
            Flow.added && Flow.added.kind === 'media'
              ? m('p.stageconfirm#media-added', [
                  m('i.material-icons', 'check'),
                  `${Flow.added.name} added — clip ${Flow.added.at} on the timeline`,
                ])
              : null,
            m(
              'ul.medialist',
              Library.items.map(item =>
                m('li.mediaitem', [
                  // A button, not an `<li>` with text on it. This list was
                  // inert: it named the media on the server and offered no
                  // way to use any of it, so the only route from "I have
                  // footage" to "it is on the timeline" was to find the bin
                  // below and drag -- an affordance with no visible cue,
                  // unavailable from the keyboard, and on a different stage
                  // from the list that told you the footage existed.
                  m(
                    'button.mediachoice',
                    {
                      title: `Add ${basename(item.name)} to the timeline`,
                      'data-media': item.name,
                      'data-kind': item.kind,
                      onclick: () => addMedia(item.name),
                    },
                    [
                      m('i.material-icons', 'add'),
                      basename(item.name),
                      // How long it runs, when the server could tell: the
                      // length the clip will arrive at.
                      item.duration
                        ? m('span.mediaduration', seconds(item.duration))
                        : null,
                    ]
                  ),
                ])
              )
            ),
          ]
        : // Not "no media" until the server has said so. Before the list
          // arrived this offered to generate demo media on a server that had
          // plenty.
          Library.loaded
          ? Generate(
              'No media on the server.',
              'Generate demo media',
              () => auth('/demo/media', { method: 'POST' }),
              'media'
            )
          : Library.retryAt
            ? m('p.stagewarn#media-unavailable', 'Could not list the media on the server.')
            : m('p.stagehint#media-loading', 'Looking for media…'),

      // Templates are material too: a title card or a colour field is made,
      // not uploaded. They were reachable only by dragging from the bin,
      // which never worked -- the timeline refused drops from it, and the
      // drop handler threw on the template's shape when one was let through.
      Bin.templates.length
        ? [
            m('h3', `Templates (${Bin.templates.length})`),
            Flow.added && Flow.added.kind === 'template'
              ? m('p.stageconfirm#template-added', [
                  m('i.material-icons', 'check'),
                  `${Flow.added.name} added — clip ${Flow.added.at} on the timeline`,
                ])
              : null,
            m(
              'ul.medialist.templatelist',
              Bin.templates.map(t =>
                m(
                  'li.mediaitem',
                  // Drawn like a media choice, but not one: `.mediachoice` is
                  // a file from the library, and a template is not a file.
                  m(
                    'button.templatechoice',
                    {
                      'data-template': t.name,
                      title: t.description
                        ? `Add a ${t.label || t.name} clip — ${t.description.replace(/\*/g, '')}`
                        : `Add a ${t.label || t.name} clip to the timeline`,
                      onclick: () => addTemplate(t),
                    },
                    [
                      m('i.material-icons', 'add'),
                      t.label || t.name,
                      t.deprecated ? m('span.deprecated', 'deprecated') : null,
                    ]
                  )
                )
              )
            ),
          ]
        : null,
    ]),
}

/** The library, loading the flow's lists as the stage panel did. */
export const Media = FlowPanel(MediaPanel)

export default Media
