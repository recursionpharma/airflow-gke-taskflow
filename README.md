# gke-taskflow

Adds support for Taskflow to the GKEStartPodOperator in Airflow.  
This allows us to write cleaner, more pythonic DAGs.

## Installation
This backage will need to be installed into the same environment as 
Airflow in order to function correctly.  For Cloud Composer, we'll have 
to [follow the docs](https://cloud.google.com/composer/docs/how-to/using/installing-python-dependencies).

### PIP

Execute the following:

```bash
pip install gke-taskflow
```

## Use
After the package is installed, you can define your task using the 
`@task.gke_pod` decorator:

```python
from datetime import datetime
from airflow.decorators import dag, task

@dag(
        schedule=None,
        start_date=datetime(2023, 7, 15),
        tags=["testing"]
)
def example_dag_taskflow():
    @task.gke_pod(
            image="python:3.10-slim",
            task_id="test_flow",
            name="test_flow",
            cluster_name="test-cluster",
            namespace="composer-internal",
            location="us-central1",
            project_id="test-cluster-123abc",
    )
    def hello_world_from_container():
        print("hello world from container")

    hello_world_from_container()

example_dag_taskflow()
```

The keyword arguments supplied to `@task.gke_pod` are identical to those 
supplied to Google's GKEStartPodOperator, on which this work is based.
The [docs for that class](https://airflow.apache.org/docs/apache-airflow-providers-google/stable/operators/cloud/kubernetes_engine.html) 
are scant, but the [source code is available 
online](https://github.com/apache/airflow/blob/main/airflow/providers/google/cloud/operators/kubernetes_engine.py#L395) for review.

