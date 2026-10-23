import m from 'mithril'
import { Edl } from '../Video'
import { TemplateParams } from '../TemplateParams'

/**
 * The selected template clip's settings: its text, length, colours, font and
 * placement (TemplateParams.js), wherever the layout puts them.
 *
 * TemplateParams draws nothing unless the clip under the playhead is a
 * template, which suits a place beside the viewer and not a panel of its own:
 * an empty panel reads as a broken one. So, given a panel, this says what
 * would appear there. `quiet` keeps the old behaviour -- nothing at all --
 * for a layout that puts these settings in a corner of something else.
 */
export const TemplateSettings = {
  view: ({ attrs }) => {
    const clip = Edl.edl[Edl.current]
    const shown = Boolean(clip) && clip.type === 'template'
    if (attrs.quiet) return m(TemplateParams)
    return m('.templatesettings', [
      m(TemplateParams),
      shown
        ? null
        : m(
            'p.panelhint#template-hint',
            'Choose a template clip on the timeline, such as a title or a colour, to change its text, length, colours and placement here.'
          ),
    ])
  },
}

export default TemplateSettings
