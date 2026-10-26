"""convert_project end to end against an in-memory stand-in for the few API calls it makes."""

import itertools
from types import SimpleNamespace as NS

import pytest
import supervisely as sly

from src.converter import convert_project

BOX = sly.ObjClass("box", sly.Rectangle)
LINE = sly.ObjClass("line", sly.Polyline)
META = sly.ProjectMeta(obj_classes=[BOX, LINE])


def info(cls, **values):
    return cls(**{**{f: None for f in cls._fields}, **values})


class FakeApi:
    """Project 10 in workspace 5: root "train" (2 images) with nested "hard" (1 image), root "empty"."""

    def __init__(self):
        self._ids = itertools.count(1000)
        self.source = info(sly.ProjectInfo, id=10, name="fruits", workspace_id=5, type="images", items_count=3)
        self.datasets = [
            info(sly.DatasetInfo, id=2, name="hard", parent_id=1),  # listed before its parent on purpose
            info(sly.DatasetInfo, id=1, name="train", parent_id=None),
            info(sly.DatasetInfo, id=3, name="empty", parent_id=None),
        ]
        self.images = {
            1: [self._image(11, "a.jpg", {"k": 1}), self._image(12, "b.jpg", {})],
            2: [self._image(21, "c.jpg", {})],
            3: [],
        }
        box = sly.Annotation((6, 8), labels=[sly.Label(sly.Rectangle(1, 1, 3, 4), BOX)])
        self.anns = {11: box.to_json(), 12: sly.Annotation((6, 8)).to_json(), 21: box.to_json()}

        self.created_projects, self.created_datasets, self.uploaded_images, self.uploaded_anns = [], [], [], []
        self.metas = {}
        self.project = NS(create=self._create_project, update_meta=self.metas.__setitem__, get_info_by_id=self._project)
        self.dataset = NS(get_list=self._list_datasets, create=self._create_dataset)
        self.image = NS(get_list=lambda ds_id: self.images[ds_id], upload_ids=self._upload_ids)
        self.annotation = NS(download_batch=self._download, upload_anns=self._upload_anns)

    @staticmethod
    def _image(image_id, name, image_meta):
        return info(sly.ImageInfo, id=image_id, name=name, meta=image_meta, width=8, height=6)

    def _create_project(self, workspace_id, name, description, change_name_if_conflict):
        assert change_name_if_conflict is True
        project = info(
            sly.ProjectInfo, id=next(self._ids), name=name, workspace_id=workspace_id, description=description
        )
        self.created_projects.append(project)
        return project

    def _project(self, project_id):
        return next(p for p in self.created_projects if p.id == project_id)

    def _list_datasets(self, project_id, recursive):
        assert (project_id, recursive) == (10, True)
        return self.datasets

    def _create_dataset(self, project_id, name, parent_id):
        dataset = info(sly.DatasetInfo, id=next(self._ids), name=name, parent_id=parent_id, project_id=project_id)
        self.created_datasets.append(dataset)
        return dataset

    def _download(self, dataset_id, ids):
        assert all(i in {im.id for im in self.images[dataset_id]} for i in ids)
        return [NS(image_id=i, annotation=self.anns[i]) for i in reversed(ids)]  # order must not matter

    def _upload_ids(self, dataset_id, names, ids, metas):
        new = [info(sly.ImageInfo, id=next(self._ids), name=n) for n in names]
        self.uploaded_images.append((dataset_id, list(names), list(ids), list(metas)))
        return new

    def _upload_anns(self, image_ids, anns):
        self.uploaded_anns.extend(anns)


@pytest.fixture
def api():
    return FakeApi()


def test_copies_tree_images_and_converted_annotations(api):
    done = []
    result = convert_project(api, api.source, META, {"box": "polygon"}, progress=done.append)

    assert result.name == "fruits(new shapes)" and result.workspace_id == 5
    assert result.description == "new shapes"
    dst_meta = sly.ProjectMeta.from_json(api.metas[result.id])
    assert dst_meta.get_obj_class("box").geometry_type is sly.Polygon
    assert dst_meta.get_obj_class("line").geometry_type is sly.Polyline

    by_id = {ds.id: ds for ds in api.created_datasets}
    tree = sorted((ds.name, by_id[ds.parent_id].name if ds.parent_id else None) for ds in api.created_datasets)
    assert tree == [("empty", None), ("hard", "train"), ("train", None)]

    copied = {
        (by_id[ds_id].name, name, src_id)
        for ds_id, names, ids, _ in api.uploaded_images
        for name, src_id in zip(names, ids, strict=True)
    }
    assert copied == {("train", "a.jpg", 11), ("train", "b.jpg", 12), ("hard", "c.jpg", 21)}
    assert [{"k": 1}, {}] in [metas for *_, metas in api.uploaded_images]

    geometries = sorted(type(label.geometry).__name__ for a in api.uploaded_anns for label in a.labels)
    assert geometries == ["Polygon", "Polygon"]
    assert sum(done) == 3


def test_destination_workspace_can_be_overridden(api):
    result = convert_project(api, api.source, META, {"box": "bitmap"}, workspace_id=99)
    assert result.workspace_id == 99


def test_nothing_is_created_without_a_change(api):
    with pytest.raises(ValueError):
        convert_project(api, api.source, META, {"box": "remain unchanged"})
    assert api.created_projects == []
