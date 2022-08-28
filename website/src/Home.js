import m from 'mithril'
import './styles/home.scss'
var timeline1 =
  'https://images.squarespace-cdn.com/content/v1/5b54f2433e2d096995211b77/1597084858418-8X6LW6UDTW7LA52ZOR33/alfred-timeline.jpg?format=500w'
var timeline2 =
  'https://images.squarespace-cdn.com/content/v1/5b54f2433e2d096995211b77/1597014928858-1H9VY1CWOPV0ZATALHYH/Screenshot+from+2020-08-09+19-11-10.png?format=750w'
var imageUpload =
  'https://images.squarespace-cdn.com/content/v1/5b54f2433e2d096995211b77/1597014788791-AXD895KQ3LCMDBZYNVRP/image-asset.png?format=750w'
var rendererImage =
  'https://images.squarespace-cdn.com/content/v1/5b54f2433e2d096995211b77/1597015146812-NWUP1J4VFMV7J9148G57/image-asset.png?format=750w'

function Home() {
  return {
    view: vnode => {
      return [
        m(
          '.homeCntr',
          m('h1', 'AUTOMATED VIDEO PRODUCTION'),

          m(
            '.imgTxtCntr',
            m('img.rightImg', { src: timeline1 }),
            m(
              'form.txtBox.alfredText',
              m('.firstLine', 'Alfred '),
              'is a simple, yet powerful video tool, designed to automate and streamline video creation. ',
              m('br'),
              m('br'),
              'Leveraging the power of HTML5 video, it is designed to make editing simple from any modern browser, ',
              'including mobile devices! '
            )
          ),

          m(
            '.imgTxtCntr',
            m('img.leftImg', { src: imageUpload }),
            m(
              'form.txtBox.firstText',
              m('.firstLine', 'First, '),
              m('br'),
              'Add photos and videos from the web, or upload custom to use in your project. ',
              m('br'),
              m('br'),
              'Or, search the media browser for related content available on the web. '
            )
          ),

          m(
            '.imgTxtCntr',
            m('img.rightImg', { src: timeline2 }),
            m(
              'form.txtBox.thenText',
              m('.firstLine', 'Then, '),
              m('br'),
              "'Generate a timeline of clips that represent your video. Edit the text, resize or rearrange clips, ",
              'and preview the results instantly! ',
              m('br'),
              m('br'),
              'Or, bypass the timeline entirely and let Alfred automatically ',
              'create videos based on your content. '
            )
          ),

          m(
            '.imgTxtCntr',
            m('img.leftImg', { src: rendererImage }),
            m(
              'form.txtBox.finallyText',
              m('.firstLine', 'Finally, '),
              m('br'),
              'Render your video at multiple resolutions, frame rates, or directly upload to specific output ',
              'destinations (Facebook, YouTube, Instagram, TikTok, etc).',
              m('br'),
              m('br'),
              'Videos can be rendered in parallel, ',
              'on multiple machines, simultaneously! '
            )
          ),

          m('.imgTxtCntrs', m('hr')),

          m(
            '.imgTxtCntrs',
            m(
              '.alQuote',
              m(
                'i',
                m(
                  'q',
                  'The pictures over. Now I have to go and put it on film.'
                )
              ),
              m('.text', '— Alfred Hitchcock ')
            ),
            m(
              '.honorText',
              'Named in honor of the illustrious Hitchcock, the master of creating film by design. '
            )
          )
        ),
      ]
    },
  }
}

export default Home
