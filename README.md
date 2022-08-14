# alfred
> *"Drama is life with all the dull bits cut out."*
>
>  ~ Alfred Hitchcock

Alfred is a video editor that works even without a server, designed for quick editing from anywhere, including mobile devices!

Demo at [alfred.quaternion.media](https://alfred.quaternion.media)

## clone
`git clone --recurse-submodules git@github.com:quaternionmedia/alfred.git`


### Common commands:
#### init
Install website dependencies

`./al init`

#### dev
`./al dev`

then open http://localhost:8000

#### rebuild docker images:
`./al dev --build`

#### install package
`./al install` [package name]
`npm i` [package name]

When run with no arguments, it will reinstall npm dependencies, which might be needed if package.json has been edited or changed.

#### demo
To download the demo media (into `videos/`):

`./al demo`

Then you can render the `demo.csv` project locally.

#### documentation
To build the documentation locally with [mkdocs](https://www.mkdocs.org/)
##### install dependencies
`pip install -r requirements-docs.txt`

##### rebuild docs
`mkdocs serve`

Optional: specify a different host address with `-a`. For example:

`mkdocs serve -a 0.0.0.0:4000` will serve the documentation on all available network hosts, at port `4000`.
#### production
`./al prod`
Assumes a [traefik](https://containo.us/traefik/) instance is already running.
