<!-- SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com> -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->

# OPC UA Diagram Generator

This repository renders OPC UA type hierarchies as SVG files. The input is a
simple text file inspired by PlantUML WBS input, but the code does not use
PlantUML. It is pure Python and does not require Java or a PlantUML JAR.

`rsvg-convert` is required only for PNG generation. It converts the generated
SVG into a raster PNG and preserves SVG filters such as node shadows.

## Why?

Standard tools like Graphviz, PlantUML, and Mermaid are not able to render the
OPC UA type hierarchies with the layout and style required by the OPC
Specification. The graphical notation for OPC UA specifications is defined
in [OPC UA Part 3, Annex C](https://reference.opcfoundation.org/specs/OPC-10000-3/annex-c).

### A Typical OPC UA Type Hierarchy

![OPC UA Example](opcua.png)

### An OPC UA Collaboration Diagram

This diagram shows a BoilerType and two instances to get a more complex
collaboration diagram.

![BoilerType Example](example.png)

## Installation

Python 3 is required to render SVG files. `rsvg-convert`
is additionally required only for PNG generation. On Debian or Ubuntu, install
both with:

```sh
sudo apt install python3 librsvg2-bin
```

On Fedora:

```sh
sudo dnf install python3 librsvg2-tools
```

On Windows, Python can be installed with WinGet from PowerShell:

```powershell
winget install -e --id Python.Python.3.11
```

The Python renderer does not require PlantUML, Java, or GNU Make. PNG output
additionally requires `rsvg-convert`. On Windows, the simplest way to use
`rsvg-convert` and the bundled Makefile is through WSL. Install Debian from an
elevated PowerShell prompt, then run the Debian commands inside the WSL
terminal:

```powershell
wsl --install -d Debian
```

After restarting WSL:

```sh
sudo apt update
sudo apt install python3 librsvg2-bin make
```

You can use the Linux instructions below now also on Windows inside WSL.

## LibAvoid Bindings

Build the optional native libavoid binding with CMake. For an Adaptagrams
source checkout cloned into `./adaptagrams`, the included script uses that
checkout. Otherwise CMake fetches Adaptagrams and pybind11:

```sh
./build_libavoid_py11.sh
```

The script delegates compiler, Python, dependency-fetching, and
platform-specific linking decisions to CMake. Set `CMAKE_GENERATOR`,
`CMAKE_BUILD_DIR`, or `CMAKE_BUILD_TYPE` when needed, and pass a different
Adaptagrams checkout as the first argument.

Alternatively, invoke CMake directly:

```sh
cmake -S . -B build
cmake --build build --config Release
```

When `./adaptagrams` exists, CMake uses it instead of downloading Adaptagrams.
Use `-DOPCDIAGGEN_ADAPTAGRAMS_DIR=/path/to/adaptagrams` to select another
checkout. Disable downloads with `-DOPCDIAGGEN_FETCH_DEPENDENCIES=OFF` when
both Adaptagrams and pybind11 are already installed or otherwise supplied to
CMake.

## Usage

Render one diagram directly in a Linux shell:

```sh
./tree2svg.py opcua.puml -o opcua.svg
# show placed trunk junctions as filled debug circles
./tree2svg.py opcua.puml --show-junctions -o opcua-debug.svg
```

On Windows using PowerShell, you can use it like this:

```powershell
python tree2svg.py opcua.puml -o opcua.svg
```

The bundled Makefile demonstrates how to build multiple diagrams easily from
source. GNU Make also ensures that only diagrams whose input has changed are
regenerated.

```sh
make
```

The implementation is split into `opcdiaggen/model.py`, `parser.py`,
`layout/`, `connectors.py`, `routing.py`, and `svg.py`. Layout strategies are
replaceable per subtree through `CompositeLayout`; custom strategies implement
the `Layout` interface. `LibavoidRouter` is isolated from the data model and
renderer, so routing can be replaced without changing layout or SVG code.

Other targets:

```sh
make svg       # generate SVG files
make png       # generate *.png files
make clean     # remove generated files
```

The renderer supports arbitrary hierarchy depth. Branches grow outward
from the root, siblings are stacked vertically, and left/right connectors are
mirrored.

Additional references are rendered when the native libavoid binding is
available. If it is unavailable or fails to route, additional references are
omitted while nodes and hierarchy references are still rendered.

## Input

The input uses a type-system section with PlantUML WBS-style depth markers. Each
node may start with one of the supported node classes: `obj`, `objtype`, `var`,
`vartype`, `method`, `reftype`, `datatype`, or `view`. If the class is omitted,
it defaults to `objtype`.

```text
@starttypesystem
* obj "Root"
** Organizes obj "Objects"
*** Organizes var "Temperature"
** Organizes obj "Types"
** Organizes obj "Views"
@endtypesystem
```

Blank lines between root-level groups separate columns. Nodes in the same group
are stacked vertically in that column.

When the reference type is omitted, it is inferred as follows: an object to an
object type uses `hasTypeDefinition`, an object to an object uses
`hasComponent`, an object or object type to a variable uses `hasProperty`, and
all other relationships use inheritance. Put an explicit reference type before
the node class when a different relationship is required.

Nodes may have optional markdown-style IDs, which can be used by additional
references:

```text
*** var "Foo" {#foo}
*** var "Bar" {#bar}
ref AssociatedWith foo - bar
ref AssociatedWith [r] foo - bar [l]
```

Anchor points are selected automatically or can be specified with `[t]` (top),
`[b]` (bottom), `[l]` (left), or `[r]` (right).

Node styling is read from the relevant `skinparam` settings. Shadows are
mandatory for type nodes and are not configurable; instance nodes do not have
shadows.

The minimum node width defaults to 230 pixels and can be changed with
`skinparam nodeMinWidth 180`. Nodes expand beyond that width when their labels
need more space.

Instance nodes use a white-to-gray gradient and type nodes use `#e8eef7` by
default. These colors can be customized with `InstanceFill`, `InstanceFillEnd`,
and `TypeFill` inside `skinparam node { ... }`.

Line and border thickness defaults to 1.3 and can be changed with
`skinparam nodeStrokeWidth 2`.

## License

The renderer is licensed under the GNU General Public License, version 3 only.
The example diagram and its generated files are licensed under the MIT License.
See [LICENSE](LICENSE) and [LICENSES](LICENSES) for the complete license texts.
