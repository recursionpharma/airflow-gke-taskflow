# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import inspect
import os
import pickle
import uuid
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import TYPE_CHECKING, Sequence, Callable, Optional

from kubernetes.client import models as k8s

from airflow.decorators.base import DecoratedOperator, TaskDecorator, task_decorator_factory
from airflow.providers.google.cloud.operators.kubernetes_engine import (
    GKEStartPodOperator,
)
from airflow.providers.cncf.kubernetes.python_kubernetes_script import (
    remove_task_decorator,
    write_python_script,
)

if TYPE_CHECKING:
    from airflow.decorators.base import Context

_PYTHON_SCRIPT_ENV = "__PYTHON_SCRIPT"

_FILENAME_IN_CONTAINER = "/tmp/script.py"


def _generate_decode_command() -> str:
    return (
        f'python -c "import base64, os;'
        rf"x = os.environ[\"{_PYTHON_SCRIPT_ENV}\"];"
        rf'f = open(\"{_FILENAME_IN_CONTAINER}\", \"w\"); f.write(x); f.close()"'
    )


def _read_file_contents(filename):
    with open(filename) as script_file:
        return script_file.read()


class _GKETaskflowOperator(DecoratedOperator, GKEStartPodOperator):
    custom_operator_name = "@task.gke_pod"

    template_fields: Sequence[str] = ("op_args", "op_kwargs")

    # since we won't mutate the arguments, we should just do the shallow copy
    # there are some cases we can't deepcopy the objects (e.g protobuf).
    shallow_copy_attrs: Sequence[str] = ("python_callable",)

    def __init__(self, namespace: str = "default", **kwargs) -> None:
        self.pickling_library = pickle
        super().__init__(
            namespace=namespace,
            name=kwargs.pop("name", f"k8s_airflow_pod_{uuid.uuid4().hex}"),
            cmds=["bash"],
            arguments=["-cx", f"{_generate_decode_command()} && python {_FILENAME_IN_CONTAINER}"],
            **kwargs,
        )

    def _get_python_source(self):
        raw_source = inspect.getsource(self.python_callable)
        res = dedent(raw_source)
        res = remove_task_decorator(res, "@task.gke_pod")
        return res

    def execute(self, context: "Context"):
        with TemporaryDirectory(prefix="venv") as tmp_dir:
            script_filename = os.path.join(tmp_dir, "script.py")
            py_source = self._get_python_source()

            jinja_context = {
                "op_args": self.op_args,
                "op_kwargs": self.op_kwargs,
                "pickling_library": self.pickling_library.__name__,
                "python_callable": self.python_callable.__name__,
                "python_callable_source": py_source,
                "string_args_global": False,
            }
            write_python_script(jinja_context=jinja_context, filename=script_filename)

            self.env_vars.append(
                k8s.V1EnvVar(name=_PYTHON_SCRIPT_ENV, value=_read_file_contents(script_filename)),
            )
            return super().execute(context)


def gke_pod_task(
    python_callable: Optional[Callable] = None,
    multiple_outputs: Optional[bool] = None,
    **kwargs,
) -> "TaskDecorator":
    return task_decorator_factory(
        python_callable=python_callable,
        multiple_outputs=multiple_outputs,
        decorated_operator_class=_GKETaskflowOperator,
        **kwargs,
    )


def get_provider_info():
    return {
        "package-name": "gke-taskflow",
        "name": "GKE Taskflow",
        "description": "Exposes a Taskflow interface to the GKEStartPodOperator",
        "task-decorators": [
            {
                "name": "gke_pod",
                "class-name": "gke_taskflow.operators.gke_taskflow.gke_pod_task",
            }
        ],
    }
