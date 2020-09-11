import os
import random
import string
import supervisely_lib as sly

my_app = sly.AppService()

LENGTH = int(os.environ['modal.state.length'])


@my_app.callback("generate")
@sly.timeit
def generate_random_string(api: sly.Api, task_id, context, state, app_logger):
    rand_string = ''.join((random.choice(string.ascii_letters + string.digits)) for _ in range(LENGTH))
    rand_string = state["prefix"] + rand_string
    api.task.set_field(task_id, "data.randomString", rand_string)


@my_app.callback("preprocessing")
@sly.timeit
def preprocessing(api: sly.Api, task_id, context, state, app_logger):
    sly.logger.info("do something here")


def main():
    sly.logger.info("Script arguments from modal dialog box",  extra={"length: ": LENGTH})

    api = sly.Api.from_env()

    data = {
        "randomString": "hello!"
    }

    state = {
        "prefix": "abc_"
    }

    initial_events = [
        {
            "state": None,
            "context": None,
            "command": "preprocessing",
        }#,
        # {
        #     "state": None,
        #     "context": None,
        #     "command": "stop",
        # }
    ]

    # Run application service
    my_app.run(data=data, state=state, initial_events=initial_events)
    my_app.wait_all()


if __name__ == "__main__":
    sly.main_wrapper("main", main)