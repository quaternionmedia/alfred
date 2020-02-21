build:
run:
	@docker run --name alfred_api --rm --detach \
		-v ./api/api.py:/app/main.py -v ./api/partial.py:/app/partial.py \
		-v ./dist/:/app/dist/ -v ./videos/:/app/videos/ \
		-p 8000:81
stop:
	@docker stop alfred_api
clean-data:
clean-images:
ps:
