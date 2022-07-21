import m from 'mithril'    
import './styles/documents.scss'   

function Documents() {
    return {
        view: (vnode) => {
            return [ 
                m('h1','Documents'), 
                m('a.docLink', {href: 'https://alfred.quaternion.media/docs/'}, 'User Documentation'), //fix me, make local 
                m('a.docLink', {href: '/api'}, 'API Reference'),     
            ]
        }
    }
} 

export default Documents