"""Class-shape conversion on SDK data objects: no API, no env, no widgets."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from uuid import uuid4

import supervisely as sly
from supervisely.annotation.json_geometries_map import GET_GEOMETRY_FROM_STR

REMAIN_UNCHANGED = "remain unchanged"
NAME_SUFFIX = "(new shapes)"


def target_shapes(obj_class: sly.ObjClass) -> list[str]:
    """Shapes a class can be converted to, as geometry names (`polygon`, `bitmap`, `any`, ...)."""
    own = obj_class.geometry_type
    return [g.geometry_name() for g in own.allowed_transforms() if g is not own]


def destination_name(source_name: str) -> str:
    """The platform adds a numeric suffix when a project with this name already exists."""
    return source_name + NAME_SUFFIX


def build_destination_meta(source_meta: sly.ProjectMeta, selectors: Mapping[str, str]) -> sly.ProjectMeta:
    """Clone the meta with the selected classes switched to their new shape.

    `selectors` maps class name -> target geometry name or `REMAIN_UNCHANGED`; missing classes stay as
    they are. Raises ValueError for unknown classes, impossible targets, or when nothing changes.
    """
    unknown = set(selectors) - {c.name for c in source_meta.obj_classes}
    if unknown:
        raise ValueError(f"Classes {sorted(unknown)} are not in the project")

    classes = []
    changed = False
    for obj_class in source_meta.obj_classes:
        target = selectors.get(obj_class.name, REMAIN_UNCHANGED)
        if target in (REMAIN_UNCHANGED, obj_class.geometry_type.geometry_name()):
            classes.append(obj_class)
            continue
        if target not in target_shapes(obj_class):
            shape = obj_class.geometry_type.geometry_name()
            raise ValueError(f"Class {obj_class.name!r} ({shape}) cannot be converted to {target!r}")
        classes.append(obj_class.clone(geometry_type=GET_GEOMETRY_FROM_STR(target)))
        changed = True

    if not changed:
        raise ValueError("Select a new shape for at least one class")
    return source_meta.clone(obj_classes=sly.ObjClassCollection(classes))


def convert_annotation(
    ann: sly.Annotation,
    destination_meta: sly.ProjectMeta,
    new_binding_key: Callable[[], str] = lambda: uuid4().hex,
) -> sly.Annotation:
    """Convert the labels of the classes whose shape changed in `destination_meta`.

    - Polygon -> Multipolygon: polygons of one class that share a binding key become one Multipolygon
      (first label's tags, description and binding key kept); unbound polygons convert one by one.
    - Multipolygon -> Polygon: the parts share one binding key (the original one, or a new key when the
      Multipolygon had none) so they stay one logical object.
    - Everything else goes through the SDK geometry conversion (`Label.convert`), which can yield
      several labels (e.g. a bitmap with several blobs) or none.
    """
    groups: dict[tuple[str, str], list[sly.Label]] = {}
    for label in ann.labels:
        key = _multipolygon_group(label, _new_class(label, destination_meta))
        if key is not None:
            groups.setdefault(key, []).append(label)

    labels: list[sly.Label] = []
    for label in ann.labels:
        new_class = _new_class(label, destination_meta)
        if new_class.geometry_type == label.obj_class.geometry_type:
            labels.append(label)
            continue

        key = _multipolygon_group(label, new_class)
        if key is not None:
            group = groups[key]
            if label is group[0]:
                geometry = sly.Multipolygon([part.geometry for part in group])
                labels.append(label.clone(geometry=geometry, obj_class=new_class))
            continue

        converted = label.convert(new_class)
        if _is_split_multipolygon(label, new_class) and len(converted) > 1:
            binding_key = label.binding_key or new_binding_key()
            converted = [part.clone(binding_key=binding_key) for part in converted]
        labels.extend(converted)

    return ann.clone(labels=labels)


def changed_classes(source_meta: sly.ProjectMeta, destination_meta: sly.ProjectMeta) -> Iterable[tuple[str, str, str]]:
    """(class name, old shape, new shape) for every class whose shape differs."""
    for obj_class in source_meta.obj_classes:
        new = destination_meta.get_obj_class(obj_class.name)
        if new.geometry_type != obj_class.geometry_type:
            yield obj_class.name, obj_class.geometry_type.geometry_name(), new.geometry_type.geometry_name()


def _new_class(label: sly.Label, destination_meta: sly.ProjectMeta) -> sly.ObjClass:
    return destination_meta.get_obj_class(label.obj_class.name)


def _multipolygon_group(label: sly.Label, new_class: sly.ObjClass) -> tuple[str, str] | None:
    if label.obj_class.geometry_type is sly.Polygon and new_class.geometry_type is sly.Multipolygon:
        if label.binding_key is not None:
            return label.obj_class.name, label.binding_key
    return None


def _is_split_multipolygon(label: sly.Label, new_class: sly.ObjClass) -> bool:
    return label.obj_class.geometry_type is sly.Multipolygon and new_class.geometry_type is sly.Polygon
