PROJECT_NUMBER ?= $(shell rg -N -o "version\s*=\s*'([^']+)'" -r '$$1' ../src/preppipe/_version.py)
DOC_BUILD_DIR ?= doxygen_build

all: doxygen_build
.PHONY: doxygen_build clean showversion

showversion:
	@echo $(PROJECT_NUMBER)

doxygen_build: Doxyfile
	mkdir -p $(DOC_BUILD_DIR)
	env DOXYGEN_PROJECT_NAME=PrepPipe DOXYGEN_OUTPUT_DIR=$(DOC_BUILD_DIR)/en DOXYGEN_OUTPUT_LANGUAGE=English DOXYGEN_PROJECT_NUMBER=$(PROJECT_NUMBER) doxygen Doxyfile
	env DOXYGEN_PROJECT_NAME="语涵编译器(PrepPipe)" DOXYGEN_OUTPUT_DIR=$(DOC_BUILD_DIR)/zh_cn DOXYGEN_OUTPUT_LANGUAGE=Chinese DOXYGEN_PROJECT_NUMBER=$(PROJECT_NUMBER) doxygen Doxyfile

clean:
	rm -rf $(DOC_BUILD_DIR)

