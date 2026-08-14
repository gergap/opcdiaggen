# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only
#
# This file is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This file is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this file. If not, see <https://www.gnu.org/licenses/>.

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
SHOW_JUNCTIONS ?= 0

ifeq ($(SHOW_JUNCTIONS),1)
JUNCTION_FLAGS := --show-junctions
else
JUNCTION_FLAGS :=
endif

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
	$(PYTHON) $(TREE2SVG) $< -o $@ $(JUNCTION_FLAGS)

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
	@echo "  SHOW_JUNCTIONS    render junction debug circles when set to 1"
