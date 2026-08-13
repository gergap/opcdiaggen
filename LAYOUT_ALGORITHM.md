<!-- SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com> -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->

# Layout Algorithm

## Base Constraints

- The algorithm should always use orthogonal edges to connect nodes
- Crossing of edges should be avoided if possible.

## Grouping of references

Each node can have incoming and outgoing references.
References of the same type should be grouped into a shared trunk.
A node's bottom edge should be separated into $n+1$ equal width parts
to find the anchor points of the $n$ reference trunks as shown in this
diagram:

```
                | top anchor point
left   +--------+--------+
-------|   BoilerType    |
       +-----+-----+-----+
             |     | two bottom anchor points
```

The incoming/outgoing direction may differ from the arrow head direction.
Notable exception: HasSubtype reference, which points to the source (base type),
but technically the reference goes from base type to subtype.

- Incoming references of type HasComponent, HasProperty, and Organizes
should use the left anchor point.
- Outgoing HasTypeDefinition and incoming HasSubtype references should use the top anchor point.
  There is never more than one of these references, and they exclude each other, so one top anchor point is always sufficient.
- All other outgoing references should use the bottom anchor points.

## Layout Groups

1. Each node should first be laid out using its "aggregated" members,
which can be properties and components, referenced by HasProperty
and HasComponent references. The rightmost bottom anchor points should be used to connect the children.
The children are vertically stacked on top of each other.
These connected child nodes will naturally be placed at the shortest distance from their parent.
If no other outgoing bottom references exist the children can be grouped into a left and right column spread evenly:
    - 8 children: 4 left, 4 right
    - 7 children: 4 left, 3 right.
2. Then create a bounding box around this group of nodes.
3. Layout these node groups without overlap:
     1. Subtypes and Instances should be placed below their (base) type. The Y offset can be found by using the parent's bounding box height + the value of the `min-spacing` setting. Place them horizontally side-by-side with even spacing.
        Use bounding boxes and a global `min-spacing` setting to calculate the horizontal positions. All subtypes should have the same y coordinates. If more than 4 subtypes are given, arrange them in rows. Max. 4 groups per row. This maximum should also be configurable.
     2. Node groups referenced by Organizes references should be placed below and to the right of the parent to create a tree-like structure. Siblings are placed vertically stacked.


Stacked Children Example in two columns:
```
           +-----------------+
           |   BoilerType    |
           +-----+-----+-----+
                 |     |
+------------+   |     |   +-----------+
|  Member  1 |---+     +---|  Member 4 |
+------------+   |     |   +-----------+
+------------+   |     |   +-----------+
|  Member  2 |---+     +---|  Member 5 |
+------------+   |         +-----------+
+------------+   |
|  Member  3 |---+
+------------+

```

Subtype Example side-by-side:
```
           +-----------------+
           |   BoilerType    |
           +-----+-----+-----+
                 |     |
         +-------+     +-------+
         |                     |
+--------+--------+   +--------+--------+
|   SubType 1     |   |   SubType 2     |
+-----+-----+-----+   +--------+--------+
      |     |                  |
```
Combined Example:
```
           +-----------------+
           |   BoilerType    |
           +-----+-----+-----+
                 |     |
                 |     |   +-----------+
                 |     +---|  Member 1 |
                 |     |   +-----------+
                 |     |   +-----------+
                 |     +---|  Member 2 |
                 |         +-----------+
                 |
         +-------+-------------+
         |                     |
+--------+--------+   +--------+--------+
|   SubType 1     |   |   SubType 2     |
+-----+-----+-----+   +--------+--------+
      |     |                  |
```
## Rendering

### Node Shapes

A general rule is that _Type_ nodes have a shadow; instances do not.
_Types_ also use italic font, whereas instances use regular font.

| Node Class             | Shape                           |
|------------------------|---------------------------------|
| Object, ObjectType     | Rectangle                       |
| Variable, VariableType | Rounded Rectangle               |
| DataType               | Hexagon                         |
| ReferenceType          | Six-sided Polygon (little flag) |
| Method                 | Ellipse                         |
| View                   | Trapezoid                       |


### OPC UA Arrow Heads

UA references are rendered as edges with different arrow symbols depending on its type.

| Reference Type    | Arrow Head                                              |
|-------------------|---------------------------------------------------------|
| HasComponent      | The single hashed line has to be near the TargetNode.   |
| HasProperty       | The double hashed lines have to be near the TargetNode. |
| HasTypeDefinition | Double filled triangle. Points to the Type node.        |
| HasSubtype        | Double triangle. Points to the base type.               |

Other references can contain a label with the reference type name.
Example: `---Organizes--->`

General reference styles:
- Symmetric ReferenceTypes are represented as lines between Nodes with closed and filled arrows on both sides pointing to the connected Nodes. Near the line has to be a text containing the string-part of the BrowseName of the ReferenceType.
- Asymmetric ReferenceTypes are represented as lines between Nodes with a closed and filled arrow on the side pointing to the TargetNode. Near the line has to be a text containing the string-part of the BrowseName of the ReferenceType.
- Asymmetric ReferenceTypes that are subtypes of HierarchicalReferences should be displayed the same way as asymmetric ReferenceTypes, except that an open arrow is used.

List of HierarchicalReferences:
- HasEventSource
- HasChild
- Organizes
- AllowedSubtype
- HasNotifier
- Aggregates
- HasProperty
- HasComponent
- HasOrderedComponent
- HasStructuredComponent
- HasAddIn
- HasSubtype
- HasFieldDescription
- HasFieldDescriptionSetMandatory
- IsDisabledOptionalField

List of NonHierarchicalReferences:
- HasInterface
- IsDeprecated
- HasModellingRule
- HasTypeDefinition
- UsesDataTypeRefinement
- UsesSubtypeRestriction
- HasEncoding
- AssociatedWith (symmetric)
- GeneratesEvent
- AlwaysGeneratesEvent

### Orthogonal Edge Routing

Edges are routed orthogonal. The layout is split into two stages:

1. Nodes and hierarchical references are positioned using the layout groups and
   shared trunks described above.
2. Additional, non-hierarchical references are routed after the first layout
   attempt with libavoid, using the fixed node positions as obstacles.

The hierarchical trunks are not rerouted by libavoid. Their positions are part
of the first layout result and remain stable. Libavoid is used for additional
references because those references must adapt to the completed geometry.

#### Rules

- Edges never go through nodes.
- Edges should keep MIN_SPACING distance from nodes.
- Edges with distinct start and end points (not a common trunk) should not overlap.
  This is a problem that occurs by respecting MIN_SPACING distance from a node.
  In addition parallel edges should also keep MIN_SPACING distance.

#### Libavoid Integration

The native router is provided by the `_libavoid_py11` pybind11 extension. The
extension exposes a batch routing operation instead of the complete libavoid
C++ object model. It receives positioned node rectangles and all additional
reference endpoints, creates the native router scene, and returns orthogonal
point lists.

Each positioned node becomes a libavoid `ShapeRef` obstacle. Libavoid's
`shapeBufferDistance` is set to `MIN_SPACING`, reserving the required clearance
around every node. Each additional reference becomes a `ConnRef` attached to
per-connector `ShapeConnectionPin` objects on its source and target shapes.
Pins use the selected `[t]`, `[b]`, `[l]`, or `[r]` direction and are offset into
the node by `MIN_SPACING`. Free-point endpoints on the raw boundary are not
used because they do not account for the buffered obstacle boundary.

All additional connectors are submitted before libavoid processes the scene, so
the router can optimize them as a complete set. The routing configuration uses
the shape buffer and nudging distance, segment and crossing penalties, and
`nudgeOrthogonalSegmentsConnectedToShapes` to separate parallel paths and
reduce crossings where possible.

Returned routes are checked for intersections with buffered non-endpoint node
rectangles before rendering. If the native extension is unavailable, or if it
returns an unusable or colliding route, additional references are omitted.
Nodes and hierarchical references remain rendered.

When an additional route crosses an existing route, the SVG renderer adds a
small orthogonal bump to make the crossing distinct from a junction. The bump
is visual only and does not change the libavoid route geometry.

#### South-North Direction

This is typically used to create parent/child relations, but is not limited to this use-case.

```
     ^  arrow head
     |  segment a: vertical segment to the arrow head
     |
+----+  segment b: horizontal segment
|       segment c: vertical segment from the source node
```

Segment a) connects the edge at a node's bottom anchor point and has variable
    length (len_a >= `MIN_SPACING`).
Segment b) connects the two segment a) and c) horizontally and has variable
    length. In case of zero length a) and c) together look like one straight line.
Segment c) starts at a node's top anchor point and has a fixed length of `MIN_SPACING`.

Mirroring: If going from North to South, the segments are reversed. a) is connected
to the source node's bottom anchor point and c) is connected to the target node's
top anchor point.

#### East-West Direction

The concept is similar to North-south but goes into horizontal direction and
this consists of two horizontal segments and one vertical segment.

```
--+       segment c) horizontal segment from source node
  |       segment b) vertical segment
  |
  +-----> segment a) horizontal segment to arrow head
```

Segment a) connects the edge at a node's west anchor point and has variable
    length (len_a >= `MIN_SPACING`).
Segment b) connects the two segments a) and c) vertically and has variable
    length. In case of zero length a) and c) together look like one straight line.
Segment c) starts at a node's east anchor point as has a fixed length of MIN_SPACING.

Mirroring: If going from West to East, the segments are reversed. a) is connected
to the source node's east anchor point and c) is connected to the target node's
west anchor point.

#### Combinations

Sometime two ore more orthogonal edges are required to reach the target without
crossing other edges or nodes. One example is the connect two east anchor points
of two nodes using two East-West edges. If the start of the second edge is not 
a node, but another edge segment c) can have zero length instead of MIN_SPACING.

Example East-East:

```
+--------+ c1     +--------+ a3
| Node 1 |--+     | Node 1 |<-+
+--------+  |b1   +--------+  | b2
            +-----------------+
                   a1
```

In this example of two East-West edges 1 and 2, the segment c2 has zero length.

Example East-South:

```
+--------+ c1     +--------+
| Node 1 |--+     | Node 1 |
+--------+  |b1   +--------+
            |         ^
            |         | a2
            +---------+
                   a1
```

In this example one East-West edge (1) is combined with a South-North edge (2).
In this case the length of b2 and c2 are zero.

### Additional References

The main layout algorithm works using the given hierarchy of objects.
Additional, non-hierarchical references may be specified after the node
hierarchy. These references are routed after the nodes and main hierarchy
references have been laid out, using the libavoid integration described above.
Therefore the nodes can contain an optional ID in the format
`{#identifier}`, that is used to specify additional references.

Id Example:
```
*** hasProperty var "Pressure\n1769.00 kPa" {#boiler2_pressure}
```

Syntax:
```
ref <type> [start_anchor] <start_id> - <end_id> [end_anchor]
```

Example:
```
' additional references, automatic anchor point selection
ref AssociatedWith boiler1_pressure - boiler2_pressure
' additional references, manual anchor point selection
ref AssociatedWith [r] boiler1_temperature - boiler2_temperature [r]
```

The user may specify the optional anchor points of the start and end node. If
not specified, the first layout stage chooses a free anchor point, preferring
the side in the direction of the other node. Anchor points can only be used if
either unused, or used by the same reference type. The selected sides are then
passed to libavoid as directional shape pins and are not changed during
additional-reference routing.
