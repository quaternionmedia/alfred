import m from 'mithril'
import { Edl } from './Video'
import { Flow, current, madeFromForm } from './Stages'
import { renderState } from './RenderStatus'

/**
 * One line under the rail: where you are, and the next thing to do, with a
 * button to its stage and a link to the journey it is part of
 * (docs/journeys.md).
 */

// docs/journeys.md, where each stage's part of the walk is told.
export const JOURNEY = '/docs/journeys/'

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

/** What to say: `{text, go?: {stage, label}, anchor}`. */
export function nextStep() {
  const stage = Flow.stage()
  const project = Flow.project()
  const clips = Edl.edl.length
  const toSource = { stage: 'source', label: 'Go to Source' }

  if (!m.route.param('project')) {
    return stage === 'source'
      ? { text: 'Start here: choose a project, or generate a demo one.', anchor: 'first-video' }
      : { text: 'Start here: choose a project on Source.', go: toSource, anchor: 'first-video' }
  }
  const name = (project && project.name) || 'This project'

  if (madeFromForm(project) && stage !== 'deliver') {
    return stage === 'render'
      ? { text: 'Fill in the form, preview a frame, then render.', anchor: 'from-a-form' }
      : {
          text: `${name} is made from its form.`,
          go: { stage: 'render', label: 'Go to Render' },
          anchor: 'from-a-form',
        }
  }

  if (stage === 'source') {
    return clips
      ? {
          text: `${name}: ${plural(clips, 'clip')}. Add more, or arrange them.`,
          go: { stage: 'edit', label: 'Next: Edit' },
          anchor: 'your-own-footage',
        }
      : {
          text: `${name} is open. Add material or a template.`,
          anchor: 'your-own-footage',
        }
  }
  if (stage === 'edit') {
    return clips
      ? {
          text: 'Arrange, trim and title the clips. It saves itself.',
          go: { stage: 'render', label: 'Next: Render' },
          anchor: 'arrange-and-title',
        }
      : {
          text: 'The timeline is empty: add clips on Source.',
          go: toSource,
          anchor: 'your-own-footage',
        }
  }
  if (stage === 'render') {
    return clips
      ? {
          text: 'Choose a size, then Queue render.',
          anchor: 'render-and-deliver',
        }
      : { text: 'Nothing to render: add clips on Source.', go: toSource, anchor: 'your-own-footage' }
  }

  const latest = Flow.renders.length ? current(Flow.renders[0]) : null
  const state = latest && renderState(latest)
  if (!latest) {
    return {
      text: 'Nothing rendered yet.',
      go: { stage: 'render', label: 'Go to Render' },
      anchor: 'render-and-deliver',
    }
  }
  if (state === 'rendered') {
    return { text: 'Done: Download it, or Deliver it.', anchor: 'render-and-deliver' }
  }
  if (state === 'failed') {
    return {
      text: 'The last render failed; its row says why.',
      go: { stage: 'edit', label: 'Go to Edit' },
      anchor: 'when-something-goes-wrong',
    }
  }
  return { text: 'Rendering: the list follows it to the end.', anchor: 'render-and-deliver' }
}

export const NextStep = {
  view: () => {
    const step = nextStep()
    return m('.nextstep#next-step', { role: 'status' }, [
      m('span.nextsteptext', step.text),
      step.go
        ? m(
            'button.nextstepgo#next-step-go',
            { type: 'button', onclick: () => Flow.go(step.go.stage) },
            [step.go.label, m('i.material-icons', { 'aria-hidden': 'true' }, 'arrow_forward')]
          )
        : null,
      m(
        'a.nextstephow#next-step-how',
        {
          href: `${JOURNEY}#${step.anchor}`,
          target: '_blank',
          rel: 'noopener',
          title: 'This step in the user journeys, in a new tab',
        },
        'How?'
      ),
    ])
  },
}

export default NextStep
