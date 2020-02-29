LOCAL_PATH= #empty

ifeq ($(OS),Windows_NT)
		detected_OS := Windows
else
    detected_OS := $(shell sh -c 'uname 2>/dev/null || echo Unknown')
endif
ifeq ($(detected_OS),Windows)
    LOCAL_PATH := /$(shell pwd)
endif
ifeq ($(detected_OS),Darwin)        # Mac OS X
    LOCAL_PATH := $(shell pwd)
endif
ifeq ($(detected_OS),Linux)
    LOCAL_PATH := /$(shell pwd)
endif
ifeq ($(detected_OS),GNU)           # Debian GNU Hurd
    LOCAL_PATH := $(shell pwd)
endif

echo:
	@echo $(OS) : $(shell uname) : $(LOCAL_PATH)

init:
	@npm install
	@docker network create alfred_isolated
build:
	@make build-api
	@make build-dev
run:
	@make run-dev
	@make run-api
stop:
	# @make stop-dev
	# @make stop-api
	@docker stop alfred_dev alfred_api

clean-data:
clean-images:
ps:
	@docker ps


build-dev:
	@docker build -t alfred_dev:latest ./builder/
run-dev:
	@docker run --name=alfred_dev --rm --detach -label=alfred \
	--network=alfred_isolated \
	-v $(LOCAL_PATH):/app/ \
	-v $(LOCAL_PATH)/dist:/app/dist/ \
	-p 1234:1234 -p 1235:1235 parceldock \
	"parcel watch /app/src/* --hmr-port 1235"
stop-dev:
	@docker stop alfred_dev

build-api:
	@docker build -t alfred_api:latest ./api/
run-api:
	@docker run --name=alfred_api --rm --detach -label=alfred \
	--network=alfred_isolated \
	-v $(LOCAL_PATH)/api/:/app/ \
	-v $(LOCAL_PATH)/dist/:/app/dist/ \
	-v $(LOCAL_PATH)/videos/:/app/videos/ \
	-p 8000:80 alfred_api:latest
stop-api:
	@docker stop alfred_api
