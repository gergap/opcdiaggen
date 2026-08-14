#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

"""Render an OPC UA type-system description as SVG.

The implementation lives in the ``opcdiaggen`` package.  This module remains
as the command-line entry point and compatibility facade for existing users.
"""

import argparse

from opcdiaggen import Connector, Direction, Node, Reference, layout, parse, to_svg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("infile")
    parser.add_argument("-o", "--outfile")
    parser.add_argument("--show-junctions", action="store_true",
                        help="render placed junctions as filled debug circles")
    args = parser.parse_args()
    with open(args.infile, "r", encoding="utf-8") as source:
        root = parse(source.read())
    output = args.outfile or args.infile.rsplit(".", 1)[0] + ".svg"
    with open(output, "w", encoding="utf-8") as destination:
        destination.write(to_svg(root, show_junctions=args.show_junctions))
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
