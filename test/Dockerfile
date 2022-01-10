FROM bats/bats

RUN apk update
RUN apk add curl

ENTRYPOINT ["/tini", "--", "bash", "bats"]