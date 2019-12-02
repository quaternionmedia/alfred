import m from "mithril";

var Al = {
  view: (vnode) => {
    return [
      m('#main', 'hello!'),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", { "/": Al } );
