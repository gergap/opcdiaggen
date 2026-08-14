import unittest

import tree2svg


HEATER = '''
@starttypesystem
skinparam nodeMinWidth 180
* obj "Heater"
** HasComponent method "Start"
** HasComponent obj "Sensor"
*** HasProperty var "Temperature"
*** HasProperty var "Pressure"
** HasComponent obj "Heating Element"
*** HasProperty var "Temperature Setpoint\\n100"
*** HasProperty var "Status\\nOff"
@endtypesystem
'''


class RootAggregateLayoutTest(unittest.TestCase):
    def test_single_has_component_child_is_connected(self):
        source = '''
@starttypesystem
* obj "root"
** HasComponent obj "child"
@endtypesystem
'''
        svg = tree2svg.to_svg(tree2svg.parse(source))

        self.assertIn('M 413,44 L 413,64', svg)
        self.assertIn('M 413,64 L 528,64 L 528,84', svg)
        root = tree2svg.parse(source)
        tree2svg.layout(root)
        self.assertEqual(len(root.bottom_connectors), 1)
        self.assertEqual(len(root.children[0].left_connectors), 1)
        self.assertEqual((root.junctions[0].x, root.junctions[0].y), (413, 64))

    def test_reference_model_keeps_source_and_target(self):
        root = tree2svg.parse('''
@starttypesystem
* obj "root"
** HasComponent obj "child"
@endtypesystem
''')

        reference = root.outgoing_references[0]
        self.assertIs(reference.source, root)
        self.assertIs(reference.target, root.children[0])
        self.assertEqual(reference.reference_type, "hasComponent")

    def test_junction_debug_rendering_is_opt_in(self):
        root = tree2svg.parse('''
@starttypesystem
* obj "root"
** HasComponent obj "child"
@endtypesystem
''')

        self.assertNotIn('<circle ', tree2svg.to_svg(root))
        self.assertIn('<circle cx="413" cy="64" r="4"', tree2svg.to_svg(root, show_junctions=True))

    def test_single_branch_uses_vertical_aggregate_trunk(self):
        svg = tree2svg.to_svg(tree2svg.parse(HEATER))

        self.assertIn('M 388,44 L 388,64', svg)
        self.assertIn('M 388,64 L 478,64 L 478,324', svg)
        root = tree2svg.parse(HEATER)
        tree2svg.layout(root)
        self.assertEqual(len(root.children), 3)
        self.assertEqual(len(root.junctions), 1)
        self.assertEqual(len(root.junctions[0].references), 3)


if __name__ == "__main__":
    unittest.main()
