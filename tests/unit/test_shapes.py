import numpy as np
import pytest
import supervisely as sly

from src.core.shapes import (
    REMAIN_UNCHANGED,
    build_destination_meta,
    changed_classes,
    convert_annotation,
    destination_name,
    target_shapes,
)

H, W = 100, 100


def polygon(points, hole=None):
    exterior = [sly.PointLocation(row, col) for row, col in points]
    interior = [[sly.PointLocation(row, col) for row, col in hole]] if hole else []
    return sly.Polygon(exterior, interior)


def meta(*classes, tags=()):
    return sly.ProjectMeta(obj_classes=sly.ObjClassCollection(list(classes)), tag_metas=list(tags))


def ann(*labels, tags=()):
    return sly.Annotation((H, W), labels=list(labels), img_tags=list(tags))


def counter():
    keys = iter(f"new-{i}" for i in range(100))
    return lambda: next(keys)


SQUARE = [(5, 5), (5, 20), (20, 20), (20, 5)]
OTHER = [(30, 30), (30, 45), (45, 45), (45, 30)]
TRIANGLE = [(60, 10), (60, 20), (70, 15)]


# ---- options and naming ----


@pytest.mark.parametrize(
    ("geometry", "expected"),
    [
        (sly.Bitmap, {"alpha_mask", "any", "multipolygon", "polygon", "rectangle"}),
        (sly.Polygon, {"any", "rectangle", "bitmap", "alpha_mask", "multipolygon"}),
        (sly.Rectangle, {"alpha_mask", "any", "bitmap", "polygon", "oriented_bbox"}),
        (sly.Multipolygon, {"any", "rectangle", "bitmap", "alpha_mask", "polygon"}),
        (sly.Polyline, {"any", "rectangle", "bitmap", "polygon", "alpha_mask"}),
        (sly.GraphNodes, {"any", "rectangle"}),
        (sly.Point, {"any"}),
        (sly.AnyGeometry, set()),
    ],
)
def test_target_shapes_are_sdk_transforms_without_the_class_own_shape(geometry, expected):
    if geometry is sly.GraphNodes:
        obj_class = sly.ObjClass("kp", sly.GraphNodes, geometry_config={"nodes": {}, "edges": []})
    else:
        obj_class = sly.ObjClass("c", geometry)
    assert set(target_shapes(obj_class)) == expected


def test_destination_name_has_no_space_before_suffix():
    assert destination_name("Lemons") == "Lemons(new shapes)"


# ---- destination meta ----


def test_meta_switches_only_selected_classes_and_keeps_tags_and_colors():
    box = sly.ObjClass("box", sly.Rectangle, color=[1, 2, 3])
    mask = sly.ObjClass("mask", sly.Bitmap, color=[4, 5, 6])
    tag = sly.TagMeta("t", sly.TagValueType.NONE)
    src = meta(box, mask, tags=[tag])

    dst = build_destination_meta(src, {"box": "polygon", "mask": REMAIN_UNCHANGED})

    assert dst.get_obj_class("box").geometry_type is sly.Polygon
    assert dst.get_obj_class("box").color == [1, 2, 3]
    assert dst.get_obj_class("mask") == mask
    assert dst.get_tag_meta("t") == tag
    assert list(changed_classes(src, dst)) == [("box", "rectangle", "polygon")]


@pytest.mark.parametrize(
    "selectors",
    [
        {},
        {"box": REMAIN_UNCHANGED},
        {"box": "rectangle"},  # its own shape is the same as "remain unchanged"
    ],
)
def test_meta_requires_a_change(selectors):
    with pytest.raises(ValueError, match="at least one class"):
        build_destination_meta(meta(sly.ObjClass("box", sly.Rectangle)), selectors)


def test_meta_rejects_unknown_class_and_impossible_shape():
    src = meta(sly.ObjClass("pt", sly.Point))
    with pytest.raises(ValueError, match="not in the project"):
        build_destination_meta(src, {"nope": "any"})
    with pytest.raises(ValueError, match="cannot be converted"):
        build_destination_meta(src, {"pt": "polygon"})


# ---- annotation conversion: SDK geometry conversion ----


def test_unchanged_classes_and_image_tags_are_kept_as_is():
    box = sly.ObjClass("box", sly.Rectangle)
    poly = sly.ObjClass("poly", sly.Polygon)
    tag_meta = sly.TagMeta("t", sly.TagValueType.ANY_STRING)
    label_tag = sly.Tag(tag_meta, "on label")
    src = meta(box, poly, tags=[tag_meta])
    dst = build_destination_meta(src, {"box": "polygon"})
    keep = sly.Label(polygon(SQUARE), poly, description="kept")
    a = ann(sly.Label(sly.Rectangle(1, 2, 10, 20), box, tags=[label_tag]), keep, tags=[sly.Tag(tag_meta, "img")])

    out = convert_annotation(a, dst)

    assert [type(label.geometry) for label in out.labels] == [sly.Polygon, sly.Polygon]
    assert out.labels[0].obj_class.name == "box"
    assert out.labels[0].tags.get("t").value == "on label"
    assert out.labels[1] is keep
    assert out.img_tags.get("t").value == "img"
    assert out.img_size == (H, W)


def test_bitmap_with_two_blobs_becomes_two_polygons():
    mask = sly.ObjClass("mask", sly.Bitmap)
    data = np.zeros((H, W), dtype=bool)
    data[10:20, 10:20] = True
    data[50:60, 50:60] = True
    dst = build_destination_meta(meta(mask), {"mask": "polygon"})

    out = convert_annotation(ann(sly.Label(sly.Bitmap(data), mask)), dst)

    assert len(out.labels) == 2
    assert all(type(label.geometry) is sly.Polygon for label in out.labels)


@pytest.mark.parametrize(
    ("geometry", "target", "expected"),
    [
        (sly.Rectangle(10, 20, 30, 40), "bitmap", sly.Bitmap),
        (sly.Polyline([sly.PointLocation(1, 1), sly.PointLocation(50, 60)]), "rectangle", sly.Rectangle),
        (sly.Rectangle(10, 20, 30, 40), "any", sly.Rectangle),  # "any" keeps the geometry, changes the class
    ],
)
def test_sdk_geometry_conversion(geometry, target, expected):
    obj_class = sly.ObjClass("c", type(geometry))
    dst = build_destination_meta(meta(obj_class), {"c": target})

    out = convert_annotation(ann(sly.Label(geometry, obj_class)), dst)

    assert [type(label.geometry) for label in out.labels] == [expected]
    assert out.labels[0].obj_class == dst.get_obj_class("c")


# ---- annotation conversion: polygon <-> multipolygon with bindings ----


def test_bound_polygons_are_grouped_by_class_and_binding():
    building = sly.ObjClass("building", sly.Polygon)
    roof = sly.ObjClass("roof", sly.Polygon)
    dst = build_destination_meta(meta(building, roof), {"building": "multipolygon", "roof": "multipolygon"})
    a = ann(
        sly.Label(polygon(SQUARE), building, description="representative", binding_key="shared"),
        sly.Label(polygon(TRIANGLE), roof, binding_key="shared"),
        sly.Label(polygon(OTHER), building, binding_key="shared"),
    )

    building_label, roof_label = convert_annotation(a, dst).labels

    assert type(building_label.geometry) is sly.Multipolygon
    assert len(building_label.geometry.parts) == 2
    assert building_label.binding_key == "shared"
    assert building_label.description == "representative"
    assert type(roof_label.geometry) is sly.Multipolygon
    assert len(roof_label.geometry.parts) == 1
    assert roof_label.binding_key == "shared"


def test_unbound_polygons_become_one_part_multipolygons():
    building = sly.ObjClass("building", sly.Polygon)
    dst = build_destination_meta(meta(building), {"building": "multipolygon"})

    out = convert_annotation(ann(sly.Label(polygon(SQUARE), building), sly.Label(polygon(OTHER), building)), dst)

    assert [len(label.geometry.parts) for label in out.labels] == [1, 1]
    assert all(label.binding_key is None for label in out.labels)


def test_unbound_multipolygon_parts_receive_one_new_binding():
    building = sly.ObjClass("building", sly.Multipolygon)
    dst = build_destination_meta(meta(building), {"building": "polygon"})
    a = ann(
        sly.Label(sly.Multipolygon([polygon(SQUARE), polygon(OTHER)]), building),
        sly.Label(sly.Multipolygon([polygon(TRIANGLE), polygon(SQUARE)]), building),
    )

    out = convert_annotation(a, dst, new_binding_key=counter())

    assert [label.binding_key for label in out.labels] == ["new-0", "new-0", "new-1", "new-1"]
    assert all(type(label.geometry) is sly.Polygon for label in out.labels)


def test_one_part_multipolygon_gets_no_binding():
    building = sly.ObjClass("building", sly.Multipolygon)
    dst = build_destination_meta(meta(building), {"building": "polygon"})

    out = convert_annotation(ann(sly.Label(sly.Multipolygon([polygon(SQUARE)]), building)), dst)

    assert [label.binding_key for label in out.labels] == [None]


def test_default_new_binding_is_a_uuid_hex():
    building = sly.ObjClass("building", sly.Multipolygon)
    dst = build_destination_meta(meta(building), {"building": "polygon"})

    out = convert_annotation(ann(sly.Label(sly.Multipolygon([polygon(SQUARE), polygon(OTHER)]), building)), dst)

    keys = {label.binding_key for label in out.labels}
    assert len(keys) == 1 and len(keys.pop()) == 32


def test_polygon_multipolygon_round_trip_keeps_parts_holes_and_binding():
    building = sly.ObjClass("building", sly.Polygon)
    polygon_meta = meta(building)
    multipolygon_meta = build_destination_meta(polygon_meta, {"building": "multipolygon"})
    parts = [polygon(SQUARE, hole=[(8, 8), (8, 12), (12, 12), (12, 8)]), polygon(OTHER)]
    original = ann(*(sly.Label(part, building, binding_key="original") for part in parts))

    as_multipolygon = convert_annotation(original, multipolygon_meta)
    back = convert_annotation(as_multipolygon, build_destination_meta(multipolygon_meta, {"building": "polygon"}))

    assert len(as_multipolygon.labels) == 1
    assert [label.geometry.to_json() for label in back.labels] == [part.to_json() for part in parts]
    assert {label.binding_key for label in back.labels} == {"original"}
