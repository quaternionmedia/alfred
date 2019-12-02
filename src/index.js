import m from "mithril";
var Slider = require("./Slider")
var Timeline = require("./Timeline")

var Al = {
  view: (vnode) => {
    return [
      m('#main', 'hello!'),
      m(Slider),
      m(Timeline),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", { "/": Al } );
