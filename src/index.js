import m from "mithril";
var Slider = require("./Slider")

var Al = {
  view: (vnode) => {
    return [
      m('#main', 'hello!'),
      m(Slider),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", { "/": Al } );
