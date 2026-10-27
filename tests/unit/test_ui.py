"""The GUI in-process through Application.test_client: rendering and the Run handler."""

import asyncio

import pytest
import supervisely as sly
from supervisely.app import DataJson, StateJson
from supervisely.app.singleton import Singleton

from src.ui import ShapeConversionGui

BOX = sly.ObjClass("box", sly.Rectangle)
POINT = sly.ObjClass("pt", sly.Point)
ANY = sly.ObjClass("free", sly.AnyGeometry)
META = sly.ProjectMeta(obj_classes=[POINT, BOX, ANY])


def info(cls, **values):
    return cls(**{**{f: None for f in cls._fields}, **values})


PROJECT = info(sly.ProjectInfo, id=10, name="fruits", items_count=4, reference_image_url=None, type="images")
RESULT = info(sly.ProjectInfo, id=11, name="fruits(new shapes)", items_count=4, reference_image_url=None)


@pytest.fixture(autouse=True)
def fresh_app(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    Singleton._instances.clear()
    yield
    Singleton._instances.clear()


class Recorder:
    def __init__(self):
        self.calls, self.finished = [], []

    def convert(self, selectors, progress):
        self.calls.append(selectors)
        for _ in range(4):
            progress(1)
        return RESULT


def make(recorder):
    gui = ShapeConversionGui(PROJECT, META, recorder.convert, recorder.finished.append)
    return gui, sly.Application(layout=gui.layout)


def click(app, gui, values):
    state = dict(StateJson())
    for name, value in values.items():
        state[gui.selectors[name].widget_id] = {**state[gui.selectors[name].widget_id], "value": value}
    route = f"/{gui.run_button.widget_id}/button_clicked_cb"
    return asyncio.run(app.test_client.post(route, json={"state": state, "context": {}}))


def test_page_renders_one_selector_per_class_sorted_by_name():
    recorder = Recorder()
    gui, app = make(recorder)

    response = asyncio.run(app.test_client.get("/"))

    assert response.status_code == 200
    assert list(gui.selectors) == ["box", "free", "pt"]
    assert [i.value for i in gui.selectors["box"].get_items()][0] == "remain unchanged"
    assert "polygon" in [i.value for i in gui.selectors["box"].get_items()]
    assert [i.value for i in gui.selectors["free"].get_items()] == ["remain unchanged"]
    assert DataJson()[gui.selectors["free"].widget_id]["disabled"] is True


def test_run_without_a_transformation_shows_a_warning():
    recorder = Recorder()
    gui, app = make(recorder)

    assert click(app, gui, {}).status_code == 200

    assert recorder.calls == []
    assert StateJson()["slyAppShowDialog"] is True
    assert DataJson()["slyAppDialogMessage"] == "Please, define at least one transformation"


def test_run_converts_with_the_selected_shapes_and_shows_the_result():
    recorder = Recorder()
    gui, app = make(recorder)

    assert click(app, gui, {"box": "polygon", "pt": "any"}).status_code == 200

    assert recorder.calls == [{"box": "polygon", "free": "remain unchanged", "pt": "any"}]
    assert recorder.finished == [RESULT]
    assert DataJson()[gui.result.widget_id]["id"] == RESULT.id
    assert DataJson()[gui.run_button.widget_id]["disabled"] is True
    assert DataJson()[gui.selectors["box"].widget_id]["disabled"] is True
