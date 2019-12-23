import m from "mithril";
var Slider = require("./Slider")
var Timeline = require("./Timeline")
var resizable = require("./resizable")
var sortable = require("./sortable")

var Al = {
  view: (vnode) => {
    return [
      m('#main', 'hello!'),
      m(Slider),
      m(Timeline),
      // m(resizable),
      // m(sortable),
    ]
  }
}


console.log('sup!')

m.route(document.body, "/", { "/": Al } );
