import os
import random
import string
import supervisely_lib as sly

my_app = sly.AppService()

TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
PROJECT_ID = int(os.environ['modal.state.slyProjectId'])

ORIGINAL_META = None
REMAIN_UNCHANGED = "remain unchanged"

# from supervisely_lib.geometry.bitmap import Bitmap
# from supervisely_lib.geometry.cuboid import Cuboid
# from supervisely_lib.geometry.point import Point
# from supervisely_lib.geometry.polygon import Polygon
# from supervisely_lib.geometry.polyline import Polyline
# from supervisely_lib.geometry.rectangle import Rectangle
# from supervisely_lib.geometry.graph import GraphNodes
# from supervisely_lib.geometry.any_geometry import AnyGeometry
# from supervisely_lib.geometry.cuboid_3d import Cuboid3d
# from supervisely_lib.geometry.pointcloud import Pointcloud
# from supervisely_lib.geometry.point_3d import Point3d
# from supervisely_lib.geometry.multichannel_bitmap import MultichannelBitmap
# Bitmap, Cuboid, Point, Polygon, Polyline, Rectangle, GraphNodes, AnyGeometry,
#                      Cuboid3d, Pointcloud, Point3d, MultichannelBitmap

#@TODO: add other classes
# zmdi-help
SHAPE_TO_ICON = {
    sly.Rectangle: "zmdi zmdi-crop-din",
    sly.Bitmap: "zmdi zmdi-brush",
    sly.Polygon: "icons8-polygon",
    sly.AnyGeometry: "zmdi zmdi-grain",
    sly.Polyline: "zmdi zmdi-minus",
    sly.Point: "zmdi zmdi-dot-circle-alt"
}


def shape_to_icon(shape):
    icon = SHAPE_TO_ICON.get(shape)
    if icon is not None:
        return '<div class="shape-icon"><i class="{}" style="margin-top: 6px;"></i></div>'.format(icon)
    else:
        return '<div>{}</div>'.format("") # graph etc ...


@my_app.callback("generate")
@sly.timeit
def generate_random_string(api: sly.Api, task_id, context, state, app_logger):
    rand_string = ''.join((random.choice(string.ascii_letters + string.digits)) for _ in range(LENGTH))
    rand_string = state["prefix"] + rand_string
    api.task.set_field(task_id, "data.randomString", rand_string)


@my_app.callback("preprocessing")
@sly.timeit
def preprocessing(api: sly.Api, task_id, context, state, app_logger):
    sly.logger.info("XXX something here")


def init_data_and_state(api: sly.Api):
    global ORIGINAL_META

    data = {}
    state = {}
    state["selectors"] = {}
    meta_json = api.project.get_meta(PROJECT_ID)
    ORIGINAL_META = sly.ProjectMeta.from_json(meta_json)

    class_descriptions = {}
    shape_selectors = {}
    for obj_class in ORIGINAL_META.obj_classes:
        obj_class: sly.ObjClass
        possible_shapes = []
        possible_shapes.append({"value": REMAIN_UNCHANGED, "label": REMAIN_UNCHANGED})

        transforms = obj_class.geometry_type.allowed_transformations()
        for gname in transforms:
            possible_shapes.append({"value": gname, "label": gname})

        shape_selectors[obj_class.name] = possible_shapes
        state["selectors"][obj_class.name] = REMAIN_UNCHANGED

        class_descriptions[obj_class.name] = {
            "color": sly.color.rgb2hex(obj_class.color),
            "icon": shape_to_icon(obj_class.geometry_type)
        }

    data["shapeSelectors"] = shape_selectors
    data["classDescriptions"] = class_descriptions
    return data, state



def main():
    api = sly.Api.from_env()

    data, state = init_data_and_state(api)

    initial_events = [
        {
            "state": None,
            "context": None,
            "command": "preprocessing",
        }
    ]

    tableData: [{
        date: '2016-05-03',
        name: 'Tom',
        address: 'No. 189, Grove St, Los Angeles'
    }, {
        date: '2016-05-02',
        name: 'Tom',
        address: 'No. 189, Grove St, Los Angeles'
    }, {
        date: '2016-05-04',
        name: 'Tom',
        address: 'No. 189, Grove St, Los Angeles'
    }, {
        date: '2016-05-01',
        name: 'Tom',
        address: 'No. 189, Grove St, Los Angeles'
    }]

    data["table"] = [{
        "date": '2016-05-03',
        "name": 'Tom',
        "address": 'No. 189, Grove St, Los Angeles'
    }, {
        "date": '2016-05-02',
        "name": 'Tom',
        "address": 'No. 189, Grove St, Los Angeles'
    }, {
        "date": '2016-05-04',
        "name": 'Tom',
        "address": 'No. 189, Grove St, Los Angeles'
    }, {
        "date": '2016-05-01',
        "name": 'Tom',
        "address": 'No. 189, Grove St, Los Angeles'
    }]

    # Run application service
    my_app.run(data=data, state=state, initial_events=initial_events)
    my_app.wait_all()


if __name__ == "__main__":
    sly.main_wrapper("main", main)