# Pinned by digest. Unpinned, this tracked node:current, which reached Node 26
# -- where yarn is no longer bundled. The image then fell through to running
# `node yarn install`, so `./al init`, the first command in the README, failed
# with "Cannot find module '/app/yarn'". Bump this deliberately.
FROM node@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32

WORKDIR /app

# The previous `npm upgrade -g yarn` was dropped: the base ships yarn 1.22 and
# upgrading it at build time reintroduced exactly the nondeterminism pinning
# the base is meant to remove.

# The image installs its own dependencies. It did not before -- it shipped no
# node_modules at all, and every dependency reached the container through the
# ./website:/app bind mount, i.e. from whatever the host happened to have.
#
# That is unsound the moment the host is not this container's platform. parcel
# resolves a native binding per platform: an Alpine container needs
# @parcel/rust-linux-x64-musl, and a Windows or macOS host installs a binding
# for itself and nothing else. The container then died on startup with
# "Cannot find module '@parcel/rust-linux-x64-musl'". Anyone who ran a host
# install -- which the README asks for, to get Playwright -- broke `./al dev`.
#
# Copying only the manifests first keeps this layer cached across source edits.
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

CMD ["yarn", "parcel", "build", "/app/src/index.html", "/app/src/*.svg", "/app/src/*.png"]
