import m from 'mithril'
import { auth } from '../Login'
import { User } from '../User'
import Bin, { seconds } from '../Bin'
import { Library } from '../Library'
import { Edl } from '../Video'
import { Flow, FlowPanel, Generate, addMedia, basename } from '../Stages'
import { refusalCode, requestProblem } from '../Problem'

/**
 * Media: the server's library, as a panel.
 *
 * The files on the server, each a button that puts one on the end of the
 * timeline and says where it landed, with how long it runs; a filter once the
 * list is long; a way to add files from this device, by the picker or dropped
 * on the panel, sent to `POST /media` one at a time with how far each has
 * got; and a way to take a file out of the library, `DELETE /media/{name}`,
 * asked twice. The templates are the Templates panel's (Templates.js); the
 * bin under the timeline lists both to drag (Bin.js), and steps aside while
 * this panel shows.
 *
 * An upload goes by `XMLHttpRequest` rather than `m.request`: only it reports
 * how much of a large file has gone, and a file of a few hundred megabytes
 * with no progress reads as a page that has stopped.
 */

// How many files a filter is worth.
const FILTER_FROM = 4

const ICONS = { video: 'movie', audio: 'audiotrack', image: 'image' }

/** What the panel holds between draws. */
const state = {
  filter: '',
  // The upload under way: `{name, percent}`, else null.
  uploading: null,
  // A file waiting for the word to replace the one of its name: `{file}`, else null.
  replacing: null,
  // The file whose deletion is being confirmed, by name, else null.
  deleting: null,
  // What the last upload or deletion did, in a line.
  told: null,
  error: null,
  dragging: false,
}

/** The library's files whose names hold the filter. */
const matching = () => {
  const needle = state.filter.trim().toLowerCase()
  return Library.items.filter(
    item => !needle || basename(item.name).toLowerCase().includes(needle)
  )
}

/** Whether a file is on the open timeline. */
const onTimeline = name => Edl.edl.some(clip => clip && clip.name === name)

const mediaPath = name => `/media/${String(name).split('/').map(encodeURIComponent).join('/')}`

const tell = line => {
  state.told = line
  state.error = null
}

/** Send one file to `POST /media`, reporting how far it has got. */
function send(file, replace = false) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/media${replace ? '?replace=true' : ''}`)
    if (User.token) xhr.setRequestHeader('Authorization', User.token)
    xhr.upload.onprogress = e => {
      if (!e.lengthComputable) return
      state.uploading = { name: file.name, percent: Math.round((100 * e.loaded) / e.total) }
      m.redraw()
    }
    xhr.onload = () => {
      let body = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch (e) {
        body = null
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body)
      else reject(Object.assign(new Error(xhr.statusText), { code: xhr.status, response: body }))
    }
    xhr.onerror = () => reject(new Error('no answer from the server'))
    const form = new FormData()
    form.append('file', file, file.name)
    xhr.send(form)
  })
}

/** Upload `files` one after another; the library is read again after. */
async function upload(files, replace = false) {
  if (!files.length || state.uploading) return
  state.error = null
  state.replacing = null
  for (const file of files) {
    state.uploading = { name: file.name, percent: 0 }
    m.redraw()
    try {
      const item = await send(file, replace)
      tell(`${basename(item.name)} ${replace ? 'replaced in' : 'added to'} the library`)
    } catch (err) {
      if (refusalCode(err) === 'media_exists') {
        // Asked, not assumed: the word to replace comes from a press.
        state.replacing = { file }
      } else {
        state.error = `Could not upload ${file.name}: ${requestProblem(err) || err.message || 'no answer'}`
      }
      break
    }
  }
  state.uploading = null
  m.redraw()
  await Library.load({ force: true })
}

/** Take `name` out of the library, and read the library again. */
const remove = name =>
  auth(mediaPath(name), { method: 'DELETE' })
    .then(() => {
      tell(`${basename(name)} removed from the library`)
      return Library.load({ force: true })
    })
    .catch(err => {
      state.error = `Could not delete ${basename(name)}: ${requestProblem(err) || 'no answer'}`
    })

/** The files of a drop or a pick, as an array. */
const filesOf = list => Array.from(list || [])

/** The box files are picked or dropped into. */
const Upload = {
  view: () =>
    m(
      '.mediaupload',
      {
        class: state.dragging ? 'dragging' : '',
        ondragover: e => {
          e.preventDefault()
          state.dragging = true
        },
        ondragleave: () => {
          state.dragging = false
        },
        ondrop: e => {
          e.preventDefault()
          state.dragging = false
          upload(filesOf(e.dataTransfer && e.dataTransfer.files))
        },
      },
      [
        m('label.mediauploadlabel', { for: 'media-upload' }, [
          m('i.material-icons', { 'aria-hidden': 'true' }, 'upload'),
          state.uploading
            ? `Uploading ${state.uploading.name}… ${state.uploading.percent}%`
            : 'Add files from this device, or drop them here',
        ]),
        m('input#media-upload', {
          type: 'file',
          multiple: true,
          accept: 'video/*,audio/*,image/*',
          disabled: Boolean(state.uploading),
          'aria-label': 'Add files to the library',
          onchange: e => {
            const files = filesOf(e.target.files)
            e.target.value = ''
            upload(files)
          },
        }),
        state.replacing
          ? m('p.mediaconfirm#media-replace', [
              `${state.replacing.file.name} is in the library already. `,
              m(
                'button#media-replace-yes',
                { type: 'button', onclick: () => upload([state.replacing.file], true) },
                'Replace it'
              ),
              m(
                'button#media-replace-no',
                {
                  type: 'button',
                  onclick: () => {
                    tell(`${state.replacing.file.name} kept as it was`)
                    state.replacing = null
                  },
                },
                'Keep it'
              ),
            ])
          : null,
      ]
    ),
}

/** One file: a button that adds it, what it is, and a way to delete it. */
const Item = {
  view: ({ attrs: { item } }) => {
    const name = basename(item.name)
    const confirming = state.deleting === item.name
    return m('li.mediaitem', { class: confirming ? 'confirming' : '' }, [
      m(
        'button.mediachoice',
        {
          type: 'button',
          title: `Add ${name} to the timeline`,
          'data-media': item.name,
          'data-kind': item.kind,
          onclick: () => addMedia(item.name),
        },
        [
          m('i.material-icons', { 'aria-hidden': 'true' }, 'add'),
          name,
          // How long it runs, when the server could tell: the length the clip
          // will arrive at.
          item.duration ? m('span.mediaduration', seconds(item.duration)) : null,
        ]
      ),
      m(
        'span.mediakind',
        { title: item.kind },
        m('i.material-icons', { 'aria-hidden': 'true' }, ICONS[item.kind] || 'insert_drive_file')
      ),
      confirming
        ? m('span.mediaconfirm', [
            onTimeline(item.name) ? 'It is on this timeline. ' : '',
            'Delete it? ',
            m(
              'button.mediadeleteyes',
              {
                type: 'button',
                onclick: () => {
                  state.deleting = null
                  remove(item.name)
                },
              },
              'Delete'
            ),
            m(
              'button.mediadeleteno',
              {
                type: 'button',
                onclick: () => {
                  state.deleting = null
                },
              },
              'Keep'
            ),
          ])
        : m(
            'button.mediadelete',
            {
              type: 'button',
              title: `Delete ${name} from the library`,
              'aria-label': `Delete ${name} from the library`,
              'data-media': item.name,
              onclick: () => {
                state.deleting = item.name
              },
            },
            m('i.material-icons', { 'aria-hidden': 'true' }, 'delete')
          ),
    ])
  },
}

const MediaPanel = {
  oninit: () => Bin.fill(),
  onupdate: () => Bin.fill(),
  // While this list shows, the bin under the timeline steps aside (Timeline.js).
  oncreate: () => {
    Bin.listed++
    setTimeout(m.redraw)
  },
  onremove: () => {
    Bin.listed--
    setTimeout(m.redraw)
  },
  view: () => {
    const count = Library.items.length
    const shown = matching()
    return m('.stagepanel#panel-media', [
      m('.stagehead', [
        m('h3', `Media${count ? ` (${count})` : ''}`),
        count >= FILTER_FROM
          ? m('input#media-filter.filter', {
              type: 'search',
              placeholder: 'Filter media',
              'aria-label': 'Filter media',
              value: state.filter,
              oninput: e => {
                state.filter = e.target.value
              },
            })
          : null,
      ]),
      m('p.stagehint', 'Choose a file to put it on the timeline, or add your own.'),
      m(Upload),
      state.told
        ? m('p.stageconfirm#media-told', [m('i.material-icons', 'check'), state.told])
        : null,
      state.error ? m('p.stagewarn#media-error', state.error) : null,
      Flow.added && Flow.added.kind === 'media'
        ? m('p.stageconfirm#media-added', [
            m('i.material-icons', 'check'),
            `${Flow.added.name} added — clip ${Flow.added.at} on the timeline`,
          ])
        : null,
      count
        ? shown.length
          ? m(
              'ul.medialist',
              shown.map(item => m(Item, { key: item.name, item }))
            )
          : m('p.stagehint#media-none-match', 'No file is named like that.')
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
    ])
  },
}

/** The library, loading the flow's lists as the stage panel did. */
export const Media = FlowPanel(MediaPanel)

export default Media
