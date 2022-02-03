PROJECT_NUMBER ?= "dev"


all: doxygen_build
.PHONY: doxygen_build clean


doxygen_build: Doxyfile
	mkdir -p doxygen_build
	env DOXYGEN_OUTPUT_DIRNAME=en DOXYGEN_OUTPUT_LANGUAGE=English DOXYGEN_PROJECT_NUMBER=$(PROJECT_NUMBER) doxygen Doxyfile

clean:
	rm -rf doxygen_build

