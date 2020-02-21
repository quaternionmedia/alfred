build:
run:
	@docker run --name parceldock --rm --detach \
		-v "$(pwd):/app/" -v "$(pwd)/dist/:/app/dist/" -p 1234:1234 -p 1235:1235 \
		parceldock "parcel watch /app/src/* --hmr-port 1235"
stop:
	@docker stop parceldock
clean-data:
clean-images:
ps:
