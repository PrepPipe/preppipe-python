UIC=pyside6-uic
UI_FILES=$(wildcard *.ui)
PY_FILES=$(addprefix generated/ui_, $(UI_FILES:.ui=.py))

all: $(PY_FILES)
.PHONY: clean

generated/ui_%.py: %.ui
	$(UIC) $< -o $@

clean:
	rm -f $(PY_FILES)