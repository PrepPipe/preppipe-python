GENDIR ?= _antlr_generated
ANTLR4 ?= antlr4

GRAMMARS := CommandScan CommandParse
ALLTOKENOUTPUTS := $(patsubst %, $(GENDIR)/%.tokens, $(GRAMMARS))

all: rule $(GENDIR)/__init__.py $(GENDIR)/README.txt
.PHONY: clean

$(GENDIR)/__init__.py:
	mkdir -p $(GENDIR)
	echo "" > $(GENDIR)/__init__.py

$(GENDIR)/README.txt:
	mkdir -p $(GENDIR)
	echo "This directory contains generated files only! Do not modify." > $(GENDIR)/README.txt
	echo "Version of antlr4 used:" >> $(GENDIR)/README.txt
	$(ANTLR4) 2>&1 | head -n 1 >> $(GENDIR)/README.txt
	echo "Please ensure that the installed antlr4-python3-runtime is compatible with the tool version" >> $(GENDIR)/README.txt

$(GENDIR)/%.tokens: %.g4
	mkdir -p $(GENDIR)
	$(ANTLR4) -Dlanguage=Python3 $< -o $(GENDIR) -listener -visitor

rule: $(ALLTOKENOUTPUTS)

clean:
	rm -rf $(GENDIR)

