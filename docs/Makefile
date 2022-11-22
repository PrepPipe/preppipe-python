PROJECT_NUMBER ?= "dev"
DOC_BUILD_DIR ?= doxygen_build

all: doxygen_build
.PHONY: doxygen_build clean


doxygen_build: Doxyfile
	mkdir -p $(DOC_BUILD_DIR)
	env DOXYGEN_OUTPUT_DIR=$(DOC_BUILD_DIR)/en DOXYGEN_OUTPUT_LANGUAGE=English DOXYGEN_PROJECT_NUMBER=$(PROJECT_NUMBER) doxygen Doxyfile
	env DOXYGEN_OUTPUT_DIR=$(DOC_BUILD_DIR)/zh DOXYGEN_OUTPUT_LANGUAGE=Chinese DOXYGEN_PROJECT_NUMBER=$(PROJECT_NUMBER) doxygen Doxyfile

clean:
	rm -rf $(DOC_BUILD_DIR)

