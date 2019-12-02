FROM countable/parceljs

EXPOSE 1234
EXPOSE 1235
WORKDIR /app

CMD ["parcel", "watch", "--hmr-port=1235", "/app/src/*"]
