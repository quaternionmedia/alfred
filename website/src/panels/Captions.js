import m from 'mithril'

/**
 * Captions -- a placeholder (contract K3).
 *
 * The captions work (lane X1) delivers this file's real content: the
 * project's captions, their style, importing and transcribing them. Until it
 * lands, the panel is registered and placed like every other (layout/
 * registry.js imports `./panels/Captions`, by its named `Captions` export or
 * its default), so the workspace and the phone flow already have a place for
 * it.
 */
export const Captions = {
  view: () =>
    m('.stagepanel#panel-captions', [
      m('h3', 'Captions'),
      m('p.stagehint', 'Captions for this timeline will be edited here.'),
    ]),
}

export default Captions
