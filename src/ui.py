"""GUI: source project, one shape selector per class, Run button, result project."""

from __future__ import annotations

from collections.abc import Callable

import supervisely as sly
from supervisely.app.widgets import (
    Button,
    Card,
    Container,
    ObjectClassView,
    Progress,
    ProjectThumbnail,
    Select,
    Text,
)

from src.core.shapes import REMAIN_UNCHANGED, target_shapes

# (selectors, progress callback) -> created project
ConvertFn = Callable[[dict[str, str], Callable[[int], object]], sly.ProjectInfo]


class ShapeConversionGui:
    """Widgets and the Run handler. Platform side effects come in through `convert` and `on_finished`."""

    def __init__(
        self,
        project: sly.ProjectInfo,
        meta: sly.ProjectMeta,
        convert: ConvertFn,
        on_finished: Callable[[sly.ProjectInfo], None],
    ):
        self._project = project
        self._convert = convert
        self._on_finished = on_finished

        self.selectors: dict[str, Select] = {}
        rows = []
        for obj_class in sorted(meta.obj_classes, key=lambda c: c.name):
            options = [REMAIN_UNCHANGED, *target_shapes(obj_class)]
            select = Select(items=[Select.Item(value, value) for value in options], width_px=220)
            if len(options) == 1:
                select.disable()
            self.selectors[obj_class.name] = select
            rows.append(
                Container(
                    [ObjectClassView(obj_class, show_shape_icon=True), select],
                    direction="horizontal",
                    fractions=[1, 1],
                )
            )
        classes_content = (
            Container(rows) if rows else Text("The project has no classes, there is nothing to convert.", "warning")
        )

        self.run_button = Button("Run", icon="zmdi zmdi-play")
        self.progress = Progress(hide_on_finish=True)
        self.result_text = Text("New project has been successfully created", "success")
        self.result = ProjectThumbnail()
        self.result_text.hide()
        self.result.hide()

        input_card = Card("Input", content=ProjectThumbnail(_thumbnail_info(project)))
        output_card = Card(
            "Output",
            'Result project name = original name + "(new shapes)"; the original project is not changed',
            content=Container([self.run_button, self.progress, self.result_text, self.result]),
        )
        classes_card = Card(
            "Shapes transformation",
            "Define destination shapes for one or several classes",
            content=classes_content,
        )
        self.layout = Container(
            [Container([input_card, output_card], direction="horizontal", fractions=[1, 2]), classes_card]
        )
        self.run_button.click(self.run)

    def selected(self) -> dict[str, str]:
        return {name: select.get_value() for name, select in self.selectors.items()}

    def run(self) -> None:
        selectors = self.selected()
        if all(value == REMAIN_UNCHANGED for value in selectors.values()):
            sly.app.show_dialog("Warning", "Please, define at least one transformation", status="warning")
            return

        self._set_locked(True)
        try:
            with self.progress(message="Converting images", total=self._project.items_count or 0) as bar:
                destination = self._convert(selectors, bar.update)
        except Exception:
            self._set_locked(False)
            raise
        self.run_button.hide()
        self.result.set(_thumbnail_info(destination))
        self.result.show()
        self.result_text.show()
        self._on_finished(destination)

    def _set_locked(self, locked: bool) -> None:
        widgets = [self.run_button, *(s for s in self.selectors.values() if len(s.get_items()) > 1)]
        for widget in widgets:
            if locked:
                widget.disable()
            else:
                widget.enable()


def _thumbnail_info(project: sly.ProjectInfo) -> sly.ProjectInfo:
    """ProjectThumbnail fails on a project without images (no preview url); show it without a preview."""
    if project.reference_image_url is None:
        return project._replace(reference_image_url="")
    return project
