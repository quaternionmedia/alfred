import m from 'mithril' 
import './styles/footer.scss'   
 
function Footer() {
    return {
        view: (vnode) => {
            return [  
                m('footer', 
                    m('.footer-text', "More information at " ),
                    m('a.footer-link', {href: 'https://www.quaternion.media/alfred/'}, 'quaternion.media/alfred')
                )
            ]
        }
    }
} 

export {Footer}