import m from 'mithril'
import { Flow, STAGES } from './Stages'
import { Workspace } from './layout/workspace'
import { auth } from './Login'
import { PanelRegistry } from './layout/registry'

/**
 * Take the editor to a stage of a journey: what the stage declares, in order
 * (`puts`, alfred/tour.py), each done as the control a person would use does it,
 * and only where it is not so already, so a stage can be gone to from anywhere
 * and gone to again.
 *
 *   project -- the first of `names` that Projects lists, chosen by its row
 *   stage   -- the stage chosen on the rail
 *   panel   -- the panel brought forward by its tab, where the workspace is
 *
 * Nothing here makes, renders, transcribes, sends or deletes anything: those
 * are a person's. A stage whose project is not there is stopped short of on
 * Source, where Projects makes one, and says so.
 *
 * Resolves to `{ did: [...], said, refused }`: what it did, in those terms,
 * and what the stage needs first where it stopped short.
 */
export async function putOn(puts) {
  const did = []
  for (const put of puts) {
    if (put.do === 'project') {
      const projects = Flow.projects.length ? Flow.projects : await auth('/project')
      const project = put.names
        .map(name => projects.find(p => p.name === name))
        .find(Boolean)
      if (!project) {
        if (Flow.stage() !== 'source') Flow.go('source')
        return {
          did,
          said: `Projects lists no ${put.names.join(' or ')}. ${
            put.names.includes('Demo')
              ? 'Generate a demo project, under Projects, makes one.'
              : 'A project of that name is added under Projects.'
          }`,
          refused: true,
        }
      }
      if (m.route.param('project') !== project._id) {
        m.route.set('/', { project: project._id, stage: Flow.stage() })
        did.push(`${project.name} chosen in Projects`)
      }
    } else if (put.do === 'stage') {
      if (Flow.stage() !== put.stage) {
        Flow.go(put.stage)
        const stage = STAGES.find(s => s.id === put.stage)
        did.push(`${stage ? stage.label : put.stage} chosen on the rail`)
      }
    } else if (put.do === 'panel') {
      // On a phone the stage shows its panels itself.
      if (document.getElementById('workspace')) {
        Workspace.showPanel(put.panel)
        const panel = PanelRegistry.get(put.panel)
        did.push(`${panel ? panel.title : put.panel} brought forward`)
      }
    }
  }
  return { did, said: '', refused: false }
}
