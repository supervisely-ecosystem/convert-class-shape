import os
import supervisely_lib as sly

my_app = sly.AppService()

TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
PROJECT_ID = int(os.environ['modal.state.slyProjectId'])

ORIGINAL_META = None
REMAIN_UNCHANGED = "remain unchanged"

SHAPE_TO_ICON = {
    sly.Rectangle: {"icon": "zmdi zmdi-crop-din", "color": "#ea9d22", "bg": "#fcefd9"},
    sly.Bitmap: {"icon": "zmdi zmdi-brush", "color": "#ff8461", "bg": "#ffebe3"},
    sly.Polygon: {"icon": "icons8-polygon", "color": "#2cd26e", "bg": "#d8f8e7"},
    sly.AnyGeometry: {"icon": "zmdi zmdi-grain", "color": "#e09e11", "bg": "#faf0d8"},
    sly.Polyline: {"icon": "zmdi zmdi-minus", "color": "#ceadff", "bg": "#f6ebff"},
    sly.Point: {"icon": "zmdi zmdi-dot-circle-alt", "color": "#899aff", "bg": "#edeeff"},
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
            "shapeIcon": SHAPE_TO_ICON.get(obj_class.geometry_type, UNKNOWN_ICON)
        }

        possible_shapes = []
        possible_shapes.append({"value": REMAIN_UNCHANGED, "label": REMAIN_UNCHANGED})
        transforms = obj_class.geometry_type.allowed_transformations()
        for gname in transforms:
            possible_shapes.append({"value": gname, "label": gname})

        row["convertTo"] = possible_shapes
        state["selectors"][obj_class.name] = REMAIN_UNCHANGED
        table.append(row)

    data["table"] = table
    return data, state


def main():
    api = sly.Api.from_env()
    data, state = init_data_and_state(api)

    # Run application service
    my_app.run(data=data, state=state)
    my_app.wait_all()


if __name__ == "__main__":
    sly.main_wrapper("main", main)