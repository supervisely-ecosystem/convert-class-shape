from collections import defaultdict
from typing import Callable, Dict, Optional, Tuple
from uuid import uuid4

import supervisely as sly
from supervisely.annotation.json_geometries_map import GET_GEOMETRY_FROM_STR

REMAIN_UNCHANGED = "remain unchanged"


def build_destination_meta(
    source_meta: sly.ProjectMeta, selectors: Dict[str, str]
) -> Tuple[sly.ProjectMeta, bool]:
    """Build destination meta and report whether at least one class changes shape."""
    new_classes = []
    conversion_requested = False

    for obj_class in source_meta.obj_classes:
        destination = selectors.get(obj_class.name, REMAIN_UNCHANGED)
        if destination == REMAIN_UNCHANGED:
            new_classes.append(obj_class)
            continue

        conversion_requested = True
        new_classes.append(
            obj_class.clone(geometry_type=GET_GEOMETRY_FROM_STR(destination))
        )

    destination_meta = source_meta.clone(
        obj_classes=sly.ObjClassCollection(new_classes)
    )
    return destination_meta, conversion_requested


def _polygon_group_key(label: sly.Label, new_class: sly.ObjClass):
    if (
        label.obj_class.geometry_type == sly.Polygon
        and new_class.geometry_type == sly.Multipolygon
        and label.binding_key is not None
    ):
        return label.obj_class.name, label.binding_key
    return None


def convert_annotation(
    annotation: sly.Annotation, destination_meta: sly.ProjectMeta
) -> sly.Annotation:
    """Convert an annotation while preserving polygon instance relationships.

    Bound polygons of the same class are collapsed into one Multipolygon label.
    When a Multipolygon is split, all of its polygon parts receive one shared
    binding key (a new key is generated when the Multipolygon was unbound).
    """
    polygon_groups = defaultdict(list)
    for label in annotation.labels:
        new_class = destination_meta.obj_classes.get(label.obj_class.name)
        group_key = _polygon_group_key(label, new_class)
        if group_key is not None:
            polygon_groups[group_key].append(label)

    new_labels = []
    emitted_groups = set()
    for label in annotation.labels:
        new_class = destination_meta.obj_classes.get(label.obj_class.name)
        if label.obj_class.geometry_type == new_class.geometry_type:
            new_labels.append(label)
            continue

        group_key = _polygon_group_key(label, new_class)
        if group_key is not None:
            if group_key in emitted_groups:
                continue

            grouped_labels = polygon_groups[group_key]
            multipolygon = sly.Multipolygon(
                [grouped_label.geometry for grouped_label in grouped_labels]
            )
            new_labels.append(
                grouped_labels[0].clone(
                    geometry=multipolygon,
                    obj_class=new_class,
                )
            )
            emitted_groups.add(group_key)
            continue

        converted_labels = label.convert(new_class)
        if (
            label.obj_class.geometry_type == sly.Multipolygon
            and new_class.geometry_type == sly.Polygon
            and len(converted_labels) > 1
        ):
            binding_key = label.binding_key or uuid4().hex
            converted_labels = [
                converted_label.clone(binding_key=binding_key)
                for converted_label in converted_labels
            ]
        new_labels.extend(converted_labels)

    return annotation.clone(labels=new_labels)


def convert_project(
    api: sly.Api,
    source_project_id: int,
    selectors: Dict[str, str],
    destination_name: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
):
    """Copy an image project and apply the selected class-shape conversions."""
    source_project = api.project.get_info_by_id(source_project_id)
    if source_project.type != str(sly.ProjectType.IMAGES):
        raise RuntimeError(
            "Project {!r} has type {!r}. App works only with type {!r}".format(
                source_project.name, source_project.type, sly.ProjectType.IMAGES
            )
        )

    source_meta = sly.ProjectMeta.from_json(api.project.get_meta(source_project_id))
    destination_meta, conversion_requested = build_destination_meta(
        source_meta, selectors
    )
    if not conversion_requested:
        raise ValueError("At least one class-shape conversion must be selected")

    if destination_name is None:
        destination_name = source_project.name + "(new shapes)"
    destination_project = api.project.create(
        source_project.workspace_id,
        destination_name,
        description="new shapes",
        change_name_if_conflict=True,
    )
    api.project.update_meta(destination_project.id, destination_meta.to_json())

    total = api.project.get_images_count(source_project.id)
    completed = 0
    progress = sly.Progress("Processing:", total_cnt=total)
    for dataset_info in api.dataset.get_list(source_project.id):
        destination_dataset = api.dataset.create(
            destination_project.id, dataset_info.name
        )
        image_infos = api.image.get_list(dataset_info.id)

        for image_batch in sly.batched(image_infos):
            image_names, image_ids, image_metas = zip(
                *((item.name, item.id, item.meta) for item in image_batch)
            )
            annotation_infos = api.annotation.download_batch(dataset_info.id, image_ids)
            annotations = [
                sly.Annotation.from_json(item.annotation, source_meta)
                for item in annotation_infos
            ]
            converted_annotations = [
                convert_annotation(annotation, destination_meta)
                for annotation in annotations
            ]

            new_image_infos = api.image.upload_ids(
                destination_dataset.id,
                image_names,
                image_ids,
                metas=image_metas,
            )
            new_image_ids = [item.id for item in new_image_infos]
            api.annotation.upload_anns(new_image_ids, converted_annotations)

            completed += len(image_batch)
            if progress_callback is not None:
                progress_callback(completed, total)
            progress.iters_done_report(len(image_batch))

    if total == 0 and progress_callback is not None:
        progress_callback(0, 0)

    return destination_project
