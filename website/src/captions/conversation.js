import m from 'mithril'
import { auth } from '../Login'
import { refusalCode, requestProblem } from '../Problem'
import { Transcript } from './transcript'

/**
 * What the language engine reads in the transcript: who spoke, which topics
 * were live and when, and where the talk went off (`POST
 * /project/{id}/conversation`, docs/editing-by-text.md, "Who spoke, and what
 * about"). The words are sent as they stand in the editor, so a cut, an undo
 * or a speaker named updates the reading a moment later, saved or not.
 */

// Quiet this long after the words last changed, then read them again.
const QUIET_MS = 1500

// The colours a speaker gets before the engine has given one, by order named.
const PALETTE = ['#ff6b6b', '#00d4ff', '#00ff88', '#ffd93d', '#ff8cc8', '#a8e6cf', '#ffd3a5', '#fd6c9e']

export const Conversation = {
  // The engine's own word for a paragraph nobody has named.
  NOBODY: 'Unknown',
  projectId: null,
  // 'idle' before anything, 'asking', 'read', 'no-engine' or 'failed'.
  state: 'idle',
  why: null,
  speakers: {},
  topics: [],
  tangents: [],
  // What the engine keeps the reading under; its page opens it by this.
  id: null,
  // Bumped when the reading changes; the paragraphs redraw on it.
  version: 0,
  seen: null,
  timer: null,
  inflight: null,

  reset: () => {
    clearTimeout(Conversation.timer)
    Object.assign(Conversation, {
      projectId: null,
      state: 'idle',
      why: null,
      speakers: {},
      topics: [],
      tangents: [],
      seen: null,
      timer: null,
      inflight: null,
    })
    Conversation.version++
  },

  /** Keep the reading in step with `projectId`'s words as they stand. */
  follow: projectId => {
    if ((projectId || null) !== Conversation.projectId) {
      Conversation.reset()
      Conversation.projectId = projectId || null
    }
    if (!projectId || Conversation.state === 'no-engine') return
    if (!Transcript.loaded || Transcript.projectId !== projectId) return
    if (Transcript.version === Conversation.seen) return
    Conversation.seen = Transcript.version
    clearTimeout(Conversation.timer)
    if (!Transcript.words.length) {
      Object.assign(Conversation, { state: 'idle', speakers: {}, topics: [], tangents: [] })
      return
    }
    Conversation.timer = setTimeout(() => Conversation.read(projectId), QUIET_MS)
  },

  read: projectId => {
    const words = Transcript.plainWords()
    Conversation.state = 'asking'
    m.redraw()
    const request = auth(`/project/${projectId}/conversation`, {
      method: 'POST',
      body: { words },
      background: true,
    })
    Conversation.inflight = request
    return request
      .then(answer => {
        if (Conversation.projectId !== projectId || Conversation.inflight !== request) return
        Conversation.speakers = (answer && answer.speakers) || {}
        Conversation.topics = (answer && answer.topics) || []
        Conversation.tangents = (answer && answer.tangents) || []
        Conversation.id = answer && answer.id != null ? answer.id : null
        Conversation.state = 'read'
        Conversation.why = null
      })
      .catch(err => {
        if (Conversation.projectId !== projectId || Conversation.inflight !== request) return
        const code = refusalCode(err)
        Conversation.state = code === 'language_engine_missing' ? 'no-engine' : 'failed'
        Conversation.why = requestProblem(err) || 'no answer'
      })
      .then(() => {
        if (Conversation.inflight === request) Conversation.inflight = null
        Conversation.version++
        m.redraw()
      })
  },

  /** A speaker's colour: the engine's, else one by order named; none for nobody. */
  colorOf: speaker => {
    if (!speaker) return null
    const known = Conversation.speakers[speaker]
    if (known && known.color) return known.color
    const names = []
    for (const word of Transcript.words) {
      if (word.speaker && !names.includes(word.speaker)) names.push(word.speaker)
    }
    const at = names.indexOf(speaker)
    return at < 0 ? null : PALETTE[at % PALETTE.length]
  },
}
