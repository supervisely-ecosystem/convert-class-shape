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
    meta_json = api.project.get_meta(PROJECT_ID)
    ORIGINAL_META = sly.ProjectMeta.from_json(meta_json)

    shape_selectors = {}
    for obj_class in ORIGINAL_META.obj_classes:
        obj_class: sly.ObjClass
        possible_shapes = []
        possible_shapes.append({"value": REMAIN_UNCHANGED, "label": REMAIN_UNCHANGED})

        #shape_selectors[obj_class.name] = []




def main():
    api = sly.Api.from_env()

    data = {
        "shapeSelectors": {
            "person": [
                {
                    "value": "remain unchanged",
                    "label": "remain unchanged"
                },
                {
                    "value": "polygon",
                    "label": "polygon"
                },
                {
                    "value": "bitmap",
                    "label": "bitmap"
                },
                {
                    "value": "any",
                    "label": "any shape"
                }
            ],
            "car": [
                {
                    "value": "remain unchanged",
                    "label": "remain unchanged"
                },
                {
                    "value": "rectangle",
                    "label": "rectangle"
                },
                {
                    "value": "any",
                    "label": "any shape"
                }
            ],
            "car1": [
                {
                    "value": "remain unchanged",
                    "label": "remain unchanged"
                },
                {
                    "value": "rectangle",
                    "label": "rectangle"
                },
                {
                    "value": "any",
                    "label": "any shape"
                }
            ],
            "car2": [
                {
                    "value": "remain unchanged",
                    "label": "remain unchanged"
                },
                {
                    "value": "rectangle",
                    "label": "rectangle"
                },
                {
                    "value": "any",
                    "label": "any shape"
                }
            ]
        }
    }

    state = {
        "a": "b",
        "selectors": {
            "person": "",
            "car": "",
            "car1": "",
            "car2": ""
        }
    }

    initial_events = [
        {
            "state": None,
            "context": None,
            "command": "preprocessing",
        }
    ]

    # Run application service
    my_app.run(data=data, state=state, initial_events=initial_events)
    my_app.wait_all()


if __name__ == "__main__":
    sly.main_wrapper("main", main)