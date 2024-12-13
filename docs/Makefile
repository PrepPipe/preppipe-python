PROJECT_NUMBER ?= $(shell rg -N -o "version\s*=\s*'([^']+)'" -r '$$1' ../src/preppipe/_version.py)
DOC_BUILD_DIR ?= doxygen_build
COMMON_BUILD_DIR ?= build/common
LANG_LIST = en zh_cn zh_hk
ALL_TEMPORARIES = $(foreach lang,$(LANG_LIST),$(COMMON_BUILD_DIR)/frontend_commands_$(lang).dox)

all: doxygen_build
.PHONY: doxygen_build clean showversion temporaries

showversion:
	@echo $(PROJECT_NUMBER)

$(COMMON_BUILD_DIR)/frontend_commands_%.dox:
	mkdir -p $(COMMON_BUILD_DIR)
	PREPPIPE_LANGUAGE=$* PREPPIPE_TOOL=cmddocs python3 -m preppipe.pipeline_cmd --namespace=vn --add-language-suffix-in-title --doxygen $@

temporaries : $(ALL_TEMPORARIES)

doxygen_build: Doxyfile temporaries
	mkdir -p $(DOC_BUILD_DIR)
	env DOXYGEN_PROJECT_NAME=PrepPipe DOXYGEN_OUTPUT_DIR=$(DOC_BUILD_DIR)/en DOXYGEN_OUTPUT_LANGUAGE=English DOXYGEN_PROJECT_NUMBER=$(PROJECT_NUMBER) doxygen Doxyfile
	env DOXYGEN_PROJECT_NAME="语涵编译器(PrepPipe)" DOXYGEN_OUTPUT_DIR=$(DOC_BUILD_DIR)/zh_cn DOXYGEN_OUTPUT_LANGUAGE=Chinese DOXYGEN_PROJECT_NUMBER=$(PROJECT_NUMBER) doxygen Doxyfile

clean:
	rm -rf $(DOC_BUILD_DIR) $(COMMON_BUILD_DIR)

