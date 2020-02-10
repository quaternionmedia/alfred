# alfred
> *"Drama is life with all the dull bits cut out."*
>
>  ~ Alfred Hitchcock

Alfred is a video editor that works even without a server, designed for quick editing from anywhere, including mobile devices!

Demo at [alfred.quaternion.media](https://alfred.quaternion.media)

### dev
`./alfred dev`

then open http://localhost:8000

If the docker images need to be rebuilt: `./alfred dev --build`

If package.json has changed, you might need to: `./alfred install` or `npm i`

### production
With a [traefik](https://containo.us/traefik/) instance running:
`./alfred prod`
