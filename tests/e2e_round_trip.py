"""Live API round-trip test for bound Polygon and Multipolygon conversion.

The test creates three temporary image projects in the selected workspace:
bound polygons -> Multipolygon -> bound polygons. It validates the project
metas, server-side annotation JSON, part count, bindings, and geometry fidelity,
then removes every project created by this run unless --keep-projects is set.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import numpy as np
import supervisely as sly

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from conversion import convert_project  # noqa: E402

MIN_INSTANCE_VERSION = "6.17.8"


def polygon(points, interior=None):
    exterior = [sly.PointLocation(row, col) for row, col in points]
    interiors = []
    if interior is not None:
        interiors.append([sly.PointLocation(row, col) for row, col in interior])
    return sly.Polygon(exterior, interiors)


def get_only_annotation(api, project_id):
    datasets = api.dataset.get_list(project_id)
    assert len(datasets) == 1, f"Expected one dataset, got {len(datasets)}"
    images = api.image.get_list(datasets[0].id)
    assert len(images) == 1, f"Expected one image, got {len(images)}"
    return images[0], api.annotation.download_json(images[0].id)


def geometry_payloads(annotation):
    payloads = []
    for label in annotation.labels:
        geometry_json = label.geometry.to_json()
        payloads.append(
            {
                "exterior": geometry_json["points"]["exterior"],
                "interior": geometry_json["points"]["interior"],
            }
        )
    return payloads


def polygon_payloads(polygons):
    payloads = []
    for item in polygons:
        geometry_json = item.to_json()
        payloads.append(
            {
                "exterior": geometry_json["points"]["exterior"],
                "interior": geometry_json["points"]["interior"],
            }
        )
    return payloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-id",
        type=int,
        default=os.getenv("SLY_E2E_WORKSPACE_ID"),
        required=os.getenv("SLY_E2E_WORKSPACE_ID") is None,
        help="Writable workspace for temporary test projects",
    )
    parser.add_argument(
        "--keep-projects",
        action="store_true",
        help="Do not remove temporary projects after the test",
    )
    args = parser.parse_args()

    api = sly.Api.from_env()
    assert api.is_version_supported(MIN_INSTANCE_VERSION), (
        f"Instance {api.instance_version} is older than required {MIN_INSTANCE_VERSION}"
    )

    run_id = uuid4().hex[:10]
    project_prefix = f"convert-shape-e2e-{run_id}"
    created_project_ids = []
    report = {
        "sdk_version": sly.__version__,
        "instance_version": api.instance_version,
        "workspace_id": args.workspace_id,
        "run_id": run_id,
    }

    try:
        source_project = api.project.create(
            args.workspace_id,
            f"{project_prefix}-polygons",
            type=sly.ProjectType.IMAGES,
        )
        created_project_ids.append(source_project.id)
        dataset = api.dataset.create(source_project.id, "round-trip")

        polygon_class = sly.ObjClass("building", sly.Polygon, color=[45, 210, 110])
        polygon_meta = sly.ProjectMeta(
            obj_classes=sly.ObjClassCollection([polygon_class])
        )
        api.project.update_meta(source_project.id, polygon_meta.to_json())

        image = np.zeros((128, 128, 3), dtype=np.uint8)
        image[:, :] = [30, 30, 30]
        image_info = api.image.upload_np(dataset.id, "round-trip.png", image)

        requested_binding_key = uuid4().hex
        parts = [
            polygon(
                [(10, 10), (10, 50), (50, 50), (50, 10)],
                interior=[(20, 20), (20, 30), (30, 30), (30, 20)],
            ),
            polygon([(70, 70), (70, 105), (105, 105), (105, 70)]),
        ]
        source_annotation = sly.Annotation(
            image.shape[:2],
            labels=[
                sly.Label(part, polygon_class, binding_key=requested_binding_key)
                for part in parts
            ],
        )
        api.annotation.upload_ann(image_info.id, source_annotation)
        _, source_json = get_only_annotation(api, source_project.id)
        assert len(source_json["objects"]) == 2
        assert all(item["geometryType"] == "polygon" for item in source_json["objects"])
        source_bindings = {item.get("instance") for item in source_json["objects"]}
        assert None not in source_bindings
        assert len(source_bindings) == 1
        source_binding_key = source_bindings.pop()

        multipolygon_project = convert_project(
            api,
            source_project.id,
            {"building": sly.Multipolygon.geometry_name()},
            destination_name=f"{project_prefix}-multipolygon",
        )
        created_project_ids.append(multipolygon_project.id)

        multipolygon_meta = sly.ProjectMeta.from_json(
            api.project.get_meta(multipolygon_project.id)
        )
        assert (
            multipolygon_meta.get_obj_class("building").geometry_type
            is sly.Multipolygon
        )
        multipolygon_image, multipolygon_json = get_only_annotation(
            api, multipolygon_project.id
        )
        assert len(multipolygon_json["objects"]) == 1
        multipolygon_object = multipolygon_json["objects"][0]
        assert multipolygon_object["geometryType"] == "multipolygon"
        assert len(multipolygon_object["parts"]) == 2

        polygon_project = convert_project(
            api,
            multipolygon_project.id,
            {"building": sly.Polygon.geometry_name()},
            destination_name=f"{project_prefix}-round-trip",
        )
        created_project_ids.append(polygon_project.id)

        final_meta = sly.ProjectMeta.from_json(api.project.get_meta(polygon_project.id))
        assert final_meta.get_obj_class("building").geometry_type is sly.Polygon
        _, final_json = get_only_annotation(api, polygon_project.id)
        assert len(final_json["objects"]) == 2
        assert all(item["geometryType"] == "polygon" for item in final_json["objects"])
        final_bindings = {item.get("instance") for item in final_json["objects"]}
        assert None not in final_bindings
        assert len(final_bindings) == 1

        downloaded_multipolygon = sly.Annotation.from_json(
            multipolygon_json, multipolygon_meta
        )
        final_annotation = sly.Annotation.from_json(final_json, final_meta)
        assert geometry_payloads(final_annotation) == polygon_payloads(parts)
        assert len(downloaded_multipolygon.labels[0].geometry.parts) == 2

        report.update(
            {
                "source_project_id": source_project.id,
                "multipolygon_project_id": multipolygon_project.id,
                "round_trip_project_id": polygon_project.id,
                "source_polygon_count": 2,
                "multipolygon_object_count": 1,
                "multipolygon_part_count": 2,
                "final_polygon_count": 2,
                "final_binding_count": len(final_bindings),
                "binding_relationship_preserved": True,
                "binding_key_regenerated": final_bindings != {source_binding_key},
                "geometry_round_trip_exact": True,
                "image_id_in_multipolygon_project": multipolygon_image.id,
                "status": "passed",
            }
        )
        print(json.dumps(report, indent=2))
    finally:
        if not args.keep_projects:
            known_ids = set(created_project_ids)
            for project in api.project.get_list(args.workspace_id):
                if project.name.startswith(project_prefix):
                    known_ids.add(project.id)
            for project_id in sorted(known_ids, reverse=True):
                api.project.remove(project_id)


if __name__ == "__main__":
    main()
