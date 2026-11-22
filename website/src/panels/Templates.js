import m from 'mithril'
import Bin from '../Bin'
import { Flow, FlowPanel, addTemplate } from '../Stages'

/**
 * Templates: the clips that are made rather than filed, as a panel.
 *
 * A title card, a text box, a colour field: each a button that puts one on
 * the end of the timeline and says where it landed. The files are the Media
 * panel's (Media.js); the bin under the timeline lists both to drag (Bin.js),
 * and steps aside while this panel shows.
 *
 * The templates are the bin's: it fetches them. Asked for here as well, so
 * the panel lists them wherever it sits, whether or not a bin is on screen.
 */
const TemplatesPanel = {
  oninit: () => Bin.fill(),
  onupdate: () => Bin.fill(),
  oncreate: () => {
    Bin.listed++
    setTimeout(m.redraw)
  },
  onremove: () => {
    Bin.listed--
    setTimeout(m.redraw)
  },
  view: () => {
    const offered = Bin.offered()
    return m('.stagepanel#panel-templates', [
      m('h3', `Templates${offered.length ? ` (${offered.length})` : ''}`),
      m('p.stagehint', 'Choose a template to put a clip of it on the timeline.'),
      Flow.added && Flow.added.kind === 'template'
        ? m('p.stageconfirm#template-added', [
            m('i.material-icons', 'check'),
            `${Flow.added.name} added — clip ${Flow.added.at} on the timeline`,
          ])
        : null,
      offered.length
        ? m(
            'ul.medialist.templatelist',
            offered.map(t =>
              m(
                'li.mediaitem',
                // Drawn like a media choice, but not one: `.mediachoice` is a
                // file from the library, and a template is not a file.
                m(
                  'button.templatechoice',
                  {
                    type: 'button',
                    'data-template': t.name,
                    title: t.description
                      ? `Add a ${t.label || t.name} clip — ${t.description.replace(/\*/g, '')}`
                      : `Add a ${t.label || t.name} clip to the timeline`,
                    onclick: () => addTemplate(t),
                  },
                  [m('i.material-icons', { 'aria-hidden': 'true' }, 'add'), t.label || t.name]
                )
              )
            )
          )
        : Bin.loaded
          ? m('p.stagehint#templates-loading', 'Looking for templates…')
          : null,
    ])
  },
}

/** The templates, loading the flow's lists as the stage panel did. */
export const Templates = FlowPanel(TemplatesPanel)

export default Templates
