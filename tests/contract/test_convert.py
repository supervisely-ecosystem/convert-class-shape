"""Runs the conversion against a real instance for every case in cases/.

Opt-in: SLY_CONTRACT_TESTS=1, credentials in ~/supervisely.env (SERVER_ADDRESS, API_TOKEN),
SLY_CONTRACT_PROJECT_ID (images project, only read) and SLY_CONTRACT_WORKSPACE_ID (a dedicated test
workspace: every case creates one new project there; nothing is deleted).

    SLY_CONTRACT_TESTS=1 SLY_CONTRACT_PROJECT_ID=123 SLY_CONTRACT_WORKSPACE_ID=45 pytest -m contract tests/contract
"""

import glob
import os
from collections import Counter

import pytest
import supervisely as sly
from dotenv import dotenv_values, load_dotenv

from src import platform_io
from src.converter import convert_project
from src.core.shapes import NAME_SUFFIX, target_shapes

CASES = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "..", "cases", "*.env")))

pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(os.getenv("SLY_CONTRACT_TESTS") != "1", reason="contract tests are opt-in"),
]


@pytest.fixture(scope="module")
def api():
    load_dotenv(os.path.expanduser("~/supervisely.env"))
    return sly.Api.from_env()


def tree(api, project_id):
    """{dataset path: {image name: Counter(class -> geometry types)}} and the image meta per item."""
    datasets = {ds.id: ds for ds in api.dataset.get_list(project_id, recursive=True)}

    def path(ds):
        return (path(datasets[ds.parent_id]) + "/" if ds.parent_id else "") + ds.name

    result, metas = {}, {}
    for ds in datasets.values():
        images = api.image.get_list(ds.id)
        anns = {a.image_id: a.annotation for a in api.annotation.download_batch(ds.id, [i.id for i in images])}
        result[path(ds)] = {
            i.name: Counter((o["classTitle"], o["geometryType"]) for o in anns[i.id]["objects"]) for i in images
        }
        metas.update({(path(ds), i.name): i.meta for i in images})
    return result, metas


@pytest.mark.parametrize("case", CASES, ids=os.path.basename)
def test_case_creates_a_converted_copy(case, api):
    project_id = int(os.environ["SLY_CONTRACT_PROJECT_ID"])
    workspace_id = int(os.environ["SLY_CONTRACT_WORKSPACE_ID"])
    preferences = dotenv_values(case)["CONVERT_TO"].split(",")
    project, meta = platform_io.get_project(api, project_id)
    selectors = {}
    for obj_class in meta.obj_classes:
        options = target_shapes(obj_class)
        chosen = next((shape for shape in preferences if shape in options), None)
        if chosen:
            selectors[obj_class.name] = chosen
    if not selectors:
        pytest.skip(f"no class of project {project_id} converts to {preferences}")
    source_before, source_metas = tree(api, project_id)

    result = convert_project(api, project, meta, selectors, workspace_id=workspace_id)

    assert result.name.startswith(project.name + NAME_SUFFIX)
    assert result.workspace_id == workspace_id
    new_meta = sly.ProjectMeta.from_json(api.project.get_meta(result.id))
    for obj_class in meta.obj_classes:
        expected = selectors.get(obj_class.name, obj_class.geometry_type.geometry_name())
        assert new_meta.get_obj_class(obj_class.name).geometry_type.geometry_name() == expected

    converted, converted_metas = tree(api, result.id)
    assert {ds: set(images) for ds, images in converted.items()} == {
        ds: set(images) for ds, images in source_before.items()
    }
    assert converted_metas == source_metas

    def unchanged(objects: Counter) -> Counter:
        return Counter({key: n for key, n in objects.items() if key[0] not in selectors})

    for ds, images in converted.items():
        for name, objects in images.items():
            for cls, geometry in objects:
                assert geometry == selectors.get(cls, geometry), (ds, name, cls)
            assert unchanged(objects) == unchanged(source_before[ds][name])

    assert tree(api, project_id)[0] == source_before, "the source project must not change"
