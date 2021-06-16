FROM node:14

# RUN apk add util-linux make python gcc
WORKDIR /app
RUN npm upgrade -g yarn
CMD ["yarn", "parcel", "build", "/app/src/index.html"]
