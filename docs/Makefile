PROJECT_NUMBER ?= $(shell rg -N -o "version\s*=\s*'([^']+)'" -r '$$1' ../src/preppipe/_version.py)
DOC_BUILD_DIR ?= doxygen_build
COMMON_BUILD_DIR ?= build/common

all: doxygen_build
.PHONY: doxygen_build clean showversion tmporaries

showversion:
	@echo $(PROJECT_NUMBER)

tmporaries:
	mkdir -p $(COMMON_BUILD_DIR)
	PREPPIPE_LANGUAGE=en    python3 scripts/frontendcommanddocs.py --namespace=vn --doxygen $(COMMON_BUILD_DIR)/frontend_commands_en.dox
	PREPPIPE_LANGUAGE=zh_cn python3 scripts/frontendcommanddocs.py --namespace=vn --doxygen $(COMMON_BUILD_DIR)/frontend_commands_zh_cn.dox
	PREPPIPE_LANGUAGE=zh_hk python3 scripts/frontendcommanddocs.py --namespace=vn --doxygen $(COMMON_BUILD_DIR)/frontend_commands_zh_hk.dox

doxygen_build: Doxyfile tmporaries
	mkdir -p $(DOC_BUILD_DIR)
	env DOXYGEN_PROJECT_NAME=PrepPipe DOXYGEN_OUTPUT_DIR=$(DOC_BUILD_DIR)/en DOXYGEN_OUTPUT_LANGUAGE=English DOXYGEN_PROJECT_NUMBER=$(PROJECT_NUMBER) doxygen Doxyfile
	env DOXYGEN_PROJECT_NAME="语涵编译器(PrepPipe)" DOXYGEN_OUTPUT_DIR=$(DOC_BUILD_DIR)/zh_cn DOXYGEN_OUTPUT_LANGUAGE=Chinese DOXYGEN_PROJECT_NUMBER=$(PROJECT_NUMBER) doxygen Doxyfile

clean:
	rm -rf $(DOC_BUILD_DIR) $(COMMON_BUILD_DIR)

