import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import supervisely as sly  # noqa: E402

from conversion import build_destination_meta, convert_annotation  # noqa: E402


def polygon(points):
    return sly.Polygon([sly.PointLocation(row, col) for row, col in points])


class ConversionTestCase(unittest.TestCase):
    def test_bound_polygons_are_grouped_by_class_and_binding(self):
        building = sly.ObjClass("building", sly.Polygon)
        roof = sly.ObjClass("roof", sly.Polygon)
        source_meta = sly.ProjectMeta(
            obj_classes=sly.ObjClassCollection([building, roof])
        )
        destination_meta, requested = build_destination_meta(
            source_meta,
            {"building": "multipolygon", "roof": "multipolygon"},
        )

        first = polygon([(5, 5), (5, 20), (20, 20), (20, 5)])
        second = polygon([(30, 30), (30, 45), (45, 45), (45, 30)])
        roof_part = polygon([(60, 10), (60, 20), (70, 15)])
        annotation = sly.Annotation(
            (100, 100),
            labels=[
                sly.Label(
                    first, building, description="representative", binding_key="shared"
                ),
                sly.Label(roof_part, roof, binding_key="shared"),
                sly.Label(second, building, binding_key="shared"),
            ],
        )

        converted = convert_annotation(annotation, destination_meta)

        self.assertTrue(requested)
        self.assertEqual(len(converted.labels), 2)
        building_label, roof_label = converted.labels
        self.assertIs(type(building_label.geometry), sly.Multipolygon)
        self.assertEqual(len(building_label.geometry.parts), 2)
        self.assertEqual(building_label.binding_key, "shared")
        self.assertEqual(building_label.description, "representative")
        self.assertIs(type(roof_label.geometry), sly.Multipolygon)
        self.assertEqual(len(roof_label.geometry.parts), 1)
        self.assertEqual(roof_label.binding_key, "shared")

    def test_unbound_polygons_are_not_grouped(self):
        source_class = sly.ObjClass("building", sly.Polygon)
        source_meta = sly.ProjectMeta(
            obj_classes=sly.ObjClassCollection([source_class])
        )
        destination_meta, _ = build_destination_meta(
            source_meta, {"building": "multipolygon"}
        )
        annotation = sly.Annotation(
            (100, 100),
            labels=[
                sly.Label(polygon([(5, 5), (5, 20), (20, 5)]), source_class),
                sly.Label(polygon([(30, 30), (30, 45), (45, 30)]), source_class),
            ],
        )

        converted = convert_annotation(annotation, destination_meta)

        self.assertEqual(len(converted.labels), 2)
        self.assertTrue(
            all(len(label.geometry.parts) == 1 for label in converted.labels)
        )
        self.assertTrue(all(label.binding_key is None for label in converted.labels))

    def test_multipolygon_parts_receive_one_binding(self):
        source_class = sly.ObjClass("building", sly.Multipolygon)
        destination_class = sly.ObjClass("building", sly.Polygon)
        destination_meta = sly.ProjectMeta(
            obj_classes=sly.ObjClassCollection([destination_class])
        )
        parts = [
            polygon([(5, 5), (5, 20), (20, 5)]),
            polygon([(30, 30), (30, 45), (45, 30)]),
        ]
        annotation = sly.Annotation(
            (100, 100),
            labels=[sly.Label(sly.Multipolygon(parts), source_class)],
        )

        converted = convert_annotation(annotation, destination_meta)

        self.assertEqual(len(converted.labels), 2)
        binding_keys = {label.binding_key for label in converted.labels}
        self.assertEqual(len(binding_keys), 1)
        binding_key = binding_keys.pop()
        self.assertIsNotNone(binding_key)
        self.assertEqual(len(binding_key), 32)
        self.assertTrue(
            all(type(label.geometry) is sly.Polygon for label in converted.labels)
        )

    def test_polygon_multipolygon_round_trip_preserves_parts_and_binding(self):
        polygon_class = sly.ObjClass("building", sly.Polygon)
        polygon_meta = sly.ProjectMeta(
            obj_classes=sly.ObjClassCollection([polygon_class])
        )
        multipolygon_meta, _ = build_destination_meta(
            polygon_meta, {"building": "multipolygon"}
        )
        original_parts = [
            polygon([(5, 5), (5, 20), (20, 20), (20, 5)]),
            polygon([(30, 30), (30, 45), (45, 45), (45, 30)]),
        ]
        original = sly.Annotation(
            (100, 100),
            labels=[
                sly.Label(part, polygon_class, binding_key="original-binding")
                for part in original_parts
            ],
        )

        as_multipolygon = convert_annotation(original, multipolygon_meta)
        round_trip = convert_annotation(as_multipolygon, polygon_meta)

        self.assertEqual(len(as_multipolygon.labels), 1)
        self.assertEqual(len(as_multipolygon.labels[0].geometry.parts), 2)
        self.assertEqual(len(round_trip.labels), 2)
        self.assertEqual(
            [label.geometry.to_json() for label in round_trip.labels],
            [part.to_json() for part in original_parts],
        )
        self.assertEqual(
            {label.binding_key for label in round_trip.labels},
            {"original-binding"},
        )


if __name__ == "__main__":
    unittest.main()
