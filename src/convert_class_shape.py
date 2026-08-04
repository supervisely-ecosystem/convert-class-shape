import asyncio
import os

import supervisely as sly

import workflow as w
from conversion import (
    REMAIN_UNCHANGED,
    build_destination_meta,
    convert_project,
)

my_app = sly.AppService()

TEAM_ID = sly.env.team_id()
WORKSPACE_ID = sly.env.workspace_id()
PROJECT_ID = sly.env.project_id()

ORIGINAL_META = None

SHAPE_TO_ICON = {
    sly.Rectangle: {"icon": "zmdi zmdi-crop-din", "color": "#ea9d22", "bg": "#fcefd9"},
    sly.Bitmap: {"icon": "zmdi zmdi-brush", "color": "#ff8461", "bg": "#ffebe3"},
    sly.Polygon: {"icon": "icons8-polygon", "color": "#2cd26e", "bg": "#d8f8e7"},
    sly.Multipolygon: {"icon": "zmdi zmdi-layers", "color": "#2cd26e", "bg": "#d8f8e7"},
    sly.AnyGeometry: {"icon": "zmdi zmdi-grain", "color": "#e09e11", "bg": "#faf0d8"},
    sly.Polyline: {"icon": "zmdi zmdi-minus", "color": "#ceadff", "bg": "#f6ebff"},
    sly.Point: {
        "icon": "zmdi zmdi-dot-circle-alt",
        "color": "#899aff",
        "bg": "#edeeff",
    },
}

UNKNOWN_ICON = {"icon": "zmdi zmdi-shape", "color": "#ea9d22", "bg": "#fcefd9"}


def init_data_and_state(api: sly.Api):
    global ORIGINAL_META

    data = {}
    state = {}
    state["selectors"] = {}
    table = []

    meta_json = api.project.get_meta(PROJECT_ID)
    ORIGINAL_META = sly.ProjectMeta.from_json(meta_json)

    for obj_class in ORIGINAL_META.obj_classes:
        obj_class: sly.ObjClass
        row = {
            "name": obj_class.name,
            "color": sly.color.rgb2hex(obj_class.color),
            "shape": obj_class.geometry_type.geometry_name(),
            "shapeIcon": SHAPE_TO_ICON.get(obj_class.geometry_type, UNKNOWN_ICON),
        }

        possible_shapes = [{"value": REMAIN_UNCHANGED, "label": REMAIN_UNCHANGED}]
        transforms = obj_class.geometry_type.allowed_transforms()
        for g in transforms:
            possible_shapes.append(
                {"value": g.geometry_name(), "label": g.geometry_name()}
            )

        sly.logger.debug(
            "{!r} -> {}".format(
                obj_class.geometry_type.geometry_name(), possible_shapes
            )
        )

        row["convertTo"] = possible_shapes
        state["selectors"][obj_class.name] = REMAIN_UNCHANGED
        table.append(row)

    data["table"] = table
    data["projectId"] = PROJECT_ID

    project = api.project.get_info_by_id(PROJECT_ID)
    data["projectName"] = project.name
    data["projectPreviewUrl"] = api.image.preview_url(
        project.reference_image_url, 100, 100
    )
    return data, state


@my_app.callback("convert")
@sly.timeit
def convert(api: sly.Api, task_id, context, state, app_logger):
    api.task.set_field(task_id, "data.started", True)

    project_id = int(os.environ["modal.state.slyProjectId"])
    src_project = api.project.get_info_by_id(project_id)

    w.workflow_input(api, src_project.id)
    if src_project.type != str(sly.ProjectType.IMAGES):
        raise RuntimeError(
            "Project {!r} has type {!r}. App works only with type {!r}".format(
                src_project.name, src_project.type, sly.ProjectType.IMAGES
            )
        )

    selectors = state["selectors"]
    _, need_action = build_destination_meta(ORIGINAL_META, selectors)

    if need_action is False:
        fields = [
            {"field": "state.showWarningDialog", "payload": True},
            {
                "field": "data.started",
                "payload": False,
            },
        ]
        api.task.set_fields(task_id, fields)
        return

    def update_progress(completed, total):
        percentage = 100 if total == 0 else int(completed * 100 / total)
        api.task.set_field(task_id, "data.progress", percentage)

    dst_project = convert_project(
        api,
        src_project.id,
        selectors,
        progress_callback=update_progress,
    )

    w.workflow_output(api, dst_project.id)
    sly.logger.info(
        "Destination project is created.",
        extra={"project_id": dst_project.id, "project_name": dst_project.name},
    )
    api.task.set_output_project(task_id, dst_project.id, dst_project.name)

    # to get correct "reference_image_url"
    res_project = api.project.get_info_by_id(dst_project.id)
    fields = [
        {
            "field": "data.resultProject",
            "payload": dst_project.name,
        },
        {
            "field": "data.resultProjectId",
            "payload": dst_project.id,
        },
        {
            "field": "data.resultProjectPreviewUrl",
            "payload": api.image.preview_url(res_project.reference_image_url, 100, 100),
        },
    ]
    api.task.set_fields(task_id, fields)
    my_app.stop()


def main():
    api = sly.Api.from_env()
    data, state = init_data_and_state(api)

    data["started"] = False
    data["progress"] = 0
    data["resultProject"] = ""

    state["showWarningDialog"] = False
    # state["showFinishDialog"] = False

    # Run application service
    asyncio.set_event_loop(asyncio.new_event_loop())
    my_app.run(data=data, state=state)


if __name__ == "__main__":
    sly.main_wrapper("main", main, log_for_agent=False)
