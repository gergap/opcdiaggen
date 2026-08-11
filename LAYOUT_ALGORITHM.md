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
                | top achor point
left   +--------+--------+
-------|   BoilerType    |
       +-----+-----+-----+
             |     | two botto anchor points
```

The incoming/outgoing direction may differ from the arrow head direction.
Notable exception: HasSubtype reference, which points to the source (base type),
but technically the references goes from base type to subtype.

- Incoming references of type HasComponent, HasProperty, and Organizes
should use the left anchor point.
- Outgoing HasTypeDefinition and incoming HasSubtype references should use the top anchor point.
  There is never more than one of these references, and they exclude each other, so one top anchor point is always sufficient.
- All other outgoing references should use the bottom anchor points.

## Layout Groups

1. Each node should first be layouted using its "aggregated" members,
which can be properties and components, referenced by HasProperty
and HasComponent references. The right most bottom anchor points should be used to connect the children.
The children are vertically stacked on top of each other.
These connected child nodes naturally will be placed with the shortest distance to its parent.
If no other outgoing bottom references exist the children can be grouped into a left and right column spread evenly: 8 children: 4 left, 4 right, 7 children: 4 left, 3 right.
2. Then create a bounding box around this group of nodes.
3. Layout these node groups without overlap:
  a) Subtypes and Instances should be placed below its (base) type. The Y offset can be found be using the parent's bounding box height + the value of `min-spacing` setting. Place them horizontally side-by-side with even spacing.
    Use bounding boxes and a global `min-spacing` setting to calculate the horizontal positions. All subtypes should have the some y coordinates. If more then 4 subtypes are given arrange them in rows. Max 4 groups per row. This maximum should also be configurable.
  b) Node groups referenced by Organizes references should be placed below and right the parent to create a tree like structure. Siblings are placed vertically stacked.


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

A general rule is that _Type_ nodes have a shadow, instances have not.
_Types_ also use Italic font, whereas instances use regular font.

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

Other reference can contain a label with the reference type name.
Example: `---Organizes--->`

General reference styles:
- Symmetric ReferenceTypes are represented as lines between Nodes with closed and filled arrows on both sides pointing to the connected Nodes. Near the line has to be a text containing the string-part of the BrowseName of the ReferenceType.
- Asymmetric ReferenceTypes are represented as lines between Nodes with a closed and filled arrow on the side pointing to the TargetNode. Near the line has to be a text containing the string-part of the BrowseName of the ReferenceType.
- Asymmetric ReferenceTypes that are subtypes of HierarchicalReferences should be exposed the same way as asymmetric ReferenceTypes except that an open arrow is used.

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
