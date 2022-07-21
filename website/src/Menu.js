import m, { render } from 'mithril'  
import { message } from 'alertifyjs'
import { User } from './User' 
import LOGO from './assets/alWhite.png' 
import './styles/menu.scss'  
  
function setActive() {   
    //loops through all links and sets the active class to the current page
    //TODO: in future set active page in state listener
    var links = document.getElementsByClassName('menuLink')
    for (var i = 0; i < links.length; i++) {
        var link = links[i] 
        if (link.href == window.location.href) {
            link.classList.add('active') 
        } else { 
            link.classList.remove('active')
        }
    } 
}

function Menu() {
    // toggles the navContainer visibility
    var open = false
    function toggle() {
        console.log('toggling menu', open)
        open = !open
    } 

    return {
        view: (vnode) => { 
            return [  
                m('header',   
                    m('.navbutton', m('i.material-icons', {onclick: toggle}, 'menu')), 
                    m('.navContainer', {style: {width: open ? '250px' : '0px'}}, [ 
                        m(navLinks, {onclick: toggle}),
                    ]), 
                    //TODO: change logo to new image in the future when location of images is known
                    m('div.logo', m(Link, {href:'/', id: 'home-link', ...vnode.attrs}, m('img.logoImg', {src: LOGO}))),  
                    m('.menuLinks', m(Links, {onclick: setActive()})),
                    m(Link, {
                            class: 'loginLink',
                            href: User.username ? '/logout' : '/login',
                            id: 'login-link',
                            ...vnode.attrs
                        }, User.username ? 'Logout' : 'Login'
                    ),
                ),
            ]
        }
    } 
} 

//an individual link 
function Link() {
    return {
        view: (vnode) => {
            return m(m.route.Link, vnode.attrs, vnode.children)
        }
    }
} 

//the links in the menu bar
function Links() {
    return {
        view: vnode => {
            return [ 
                m(Link, {class: 'menuLink', href: '/projects', id: 'projects-link', ...vnode.attrs},'PROJECTS'),
                m(Link, {class: 'menuLink', href: '/renders', id: 'renders-link', ...vnode.attrs}, 'RENDERS'),  
                m(Link, {class: 'menuLink', href: '/documents', id: 'documents-link', ...vnode.attrs}, 'DOCUMENTS'),  
            ]
        }
    }
} 

//the links in the nav bar, separated to have own style
function navLinks() {
    return {
        view: vnode => {
        return [
            m(Link, {class: 'navLink', href: '/', id: 'home-link', ...vnode.attrs}, 'HOME'),
            m(Link, {class: 'navLink', href: '/projects', id: 'projects-link', ...vnode.attrs}, 'PROJECTS'),
            m(Link, {class: 'navLink', href: '/renders', id: 'renders-link', ...vnode.attrs}, 'RENDERS'),  
            m(Link, {class: 'navLink', href: '/documents', id: 'documents-link', ...vnode.attrs}, 'DOCUMENTS'),  
            m(Link, {
                    class: 'navLink',
                    href: User.username ? '/logout' : '/login',
                    id: 'login-link',
                    ...vnode.attrs
                }, User.username ? 'LOGOUT' : 'LOGIN'
            ),
        ]
        }
    }
}
   
export { Menu, Links, Link, navLinks, setActive }