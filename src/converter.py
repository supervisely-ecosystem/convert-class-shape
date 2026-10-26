"""Creates the converted copy of a project."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import supervisely as sly

from src import platform_io
from src.core.datasets import parents_first
from src.core.shapes import build_destination_meta, changed_classes, convert_annotation, destination_name

BATCH_SIZE = 50


def convert_project(
    api: sly.Api,
    project: sly.ProjectInfo,
    meta: sly.ProjectMeta,
    selectors: Mapping[str, str],
    workspace_id: int | None = None,
    progress: Callable[[int], object] | None = None,
) -> sly.ProjectInfo:
    """Copy `project` into a new project `<name>(new shapes)` with the selected classes converted.

    The new project goes to `workspace_id` (default: the source project's workspace) and keeps the
    dataset tree, image names and image meta. The source project is only read. `progress` is called
    with the number of images done after every batch.
    """
    destination_meta = build_destination_meta(meta, selectors)
    for name, old, new in changed_classes(meta, destination_meta):
        sly.logger.info(f"Class {name!r}: {old} -> {new}")

    target_workspace = project.workspace_id if workspace_id is None else workspace_id
    destination = platform_io.create_project(api, target_workspace, destination_name(project.name), destination_meta)
    sly.logger.info(f"Created project {destination.name!r} (id {destination.id})")

    new_dataset_ids: dict[int, int] = {}
    for dataset in parents_first(platform_io.list_datasets(api, project.id)):
        parent_id = new_dataset_ids.get(dataset.parent_id) if dataset.parent_id is not None else None
        new_dataset = platform_io.create_dataset(api, destination.id, dataset.name, parent_id)
        new_dataset_ids[dataset.id] = new_dataset.id

        images = platform_io.list_images(api, dataset.id)
        for batch in sly.batched(images, BATCH_SIZE):
            anns = platform_io.download_annotations(api, dataset.id, batch, meta)
            converted = [convert_annotation(ann, destination_meta) for ann in anns]
            platform_io.copy_images(api, new_dataset.id, batch, converted)
            if progress is not None:
                progress(len(batch))

    return platform_io.refresh_project(api, destination.id)
