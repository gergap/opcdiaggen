# Makefile for OPC UA diagram pipeline:
#   .puml  --(tree2svg.py)--->  .svg
#   .svg   --(rsvg-convert)-->  .png
#
# Usage:
#   make            # build everything found in SRC
#   make clean      # remove generated files
#   make TREE2SVG=/path/to/tree2svg.py
#
# Requirements: python3, rsvg-convert (librsvg2-bin)

# --- Configuration ------------------------------------------------------

PYTHON   ?= python3
RSVG     ?= rsvg-convert
TREE2SVG ?= tree2svg.py

# All PlantUML source files in this directory (edit SRC if you keep them
# somewhere else, e.g. SRC := diagrams/*.puml)
SRC := $(wildcard *.puml)

SVG      := $(SRC:.puml=.svg)
PNG      := $(SRC:.puml=.png)

# --- Top-level targets ---------------------------------------------------

.PHONY: all clean distclean svg png help

all: png

svg: $(SVG)
png: $(PNG)

# --- Rules ---------------------------------------------------------------

# .puml -> .svg
%.svg: %.puml $(TREE2SVG)
	$(PYTHON) $(TREE2SVG) $< -o $@

# rasterize, white background
%.png: %.svg
	$(RSVG) -b white $< -o $@

# --- Housekeeping ----------------------------------------------------------

clean:
	rm -f $(SVG) $(PNG)

distclean: clean

help:
	@echo "Targets:"
	@echo "  make          build PNGs for every .puml file (default)"
	@echo "  make svg      build only the raw PlantUML .svg files"
	@echo "  make png      build the final *.png files"
	@echo "  make clean    remove generated diagram files"
	@echo "  make distclean remove generated files"
	@echo ""
	@echo "Variables:"
	@echo "  TREE2SVG          path to tree2svg.py (default: $(TREE2SVG))"
