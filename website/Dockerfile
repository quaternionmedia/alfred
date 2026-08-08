# Pinned by digest. Unpinned, this tracked node:current, which reached Node 26
# -- where yarn is no longer bundled. The image then fell through to running
# `node yarn install`, so `./al init`, the first command in the README, failed
# with "Cannot find module '/app/yarn'". Bump this deliberately.
FROM node@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32

WORKDIR /app

# The previous `npm upgrade -g yarn` was dropped: the base ships yarn 1.22 and
# upgrading it at build time reintroduced exactly the nondeterminism pinning
# the base is meant to remove.

CMD ["yarn", "parcel", "build", "/app/src/index.html", "/app/src/*.svg", "/app/src/*.png"]
