# alfred
> *"Drama is life with all the dull bits cut out."*
>
>  ~ Alfred Hitchcock

Alfred is a video editor that works even without a server, designed for quick editing from anywhere, including mobile devices!

Demo at [alfred.quaternion.media](https://alfred.quaternion.media)

### install
`pip3 install -r requirements.txt`

### dev
`./alfred dev`

then open http://localhost:8000

If the Dockerfiles need to be rebuilt: `./alfred dev --build`

### production
With a [traefik](https://containo.us/traefik/) instance running:
`./alfred prod`
