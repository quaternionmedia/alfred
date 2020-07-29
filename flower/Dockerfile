FROM alpine
RUN apk update
RUN apk add python3
RUN apk add py-pip
RUN pip install flower

ENTRYPOINT ["flower", "--port=5555"]
