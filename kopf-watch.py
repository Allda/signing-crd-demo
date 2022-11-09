import kopf
import yaml
from kubernetes import config
from openshift.dynamic import DynamicClient
import random
from typing import Any


def launch_pipeline(crd_name: str, spec: Any) -> None:
    """
    Launch new OpenShift pipeline that signs a content given
    by signing request CRD
    """
    k8s_client = config.new_client_from_config()
    dyn_client = DynamicClient(k8s_client)

    pipelinerun_api = dyn_client.resources.get(
        api_version="tekton.dev/v1beta1", kind="PipelineRun"
    )
    crd_id = random.randint(1, 100000000)

    # Following definition creates new PipelineRun instance
    pipelinerun = f"""
    apiVersion: tekton.dev/v1beta1
    kind: PipelineRun
    metadata:
        annotations:
            pipeline.openshift.io/preferredName: crd-example-demo
            SigningRequest.name: {crd_name}
            SigningRequest.pull_spec: {spec['pull_spec']}
            SigningRequest.requestor: {spec['requestor']}
        name: crd-example-demo-{crd_id}
        labels:
            tekton.dev/pipeline: crd-example-demo
    spec:
        pipelineRef:
            name: crd-example-demo
        serviceAccountName: pipeline
        timeout: 1h0m0s
    """

    pipelinerun_data = yaml.load(pipelinerun, Loader=yaml.SafeLoader)
    pipelinerun_api.create(
        body=pipelinerun_data, namespace="araszka-signing-controller"
    )


def update_request_status(request_name, status):
    k8s_client = config.new_client_from_config()
    dyn_client = DynamicClient(k8s_client)

    # Let's update status of signing request to indicate the signing status
    v1_services = dyn_client.resources.get(api_version="v1", kind="SigningRequest")
    service = f"""

    apiVersion: redhat.com/v1
    kind: SigningRequest
    metadata:
        name: {request_name}
        annotations:
            status: {status}
    """

    service_data = yaml.load(service)
    v1_services.patch(
        body=service_data,
        namespace="araszka-signing-controller",
        content_type="application/merge-patch+json",
    )


@kopf.on.create("SigningRequest")
def create_signing_request_handler(spec: Any, name: str, **_) -> None:
    """
    A SigningRequest on creation handler
    A function is called immediately after a CRD given by kopf wrapper

    Args:
        spec (Any): Specification of CRD
        name (str): A name of CRD
    """

    print(f"Created {name} with spec: {spec}")

    update_request_status(name, "in-progress")

    launch_pipeline(name, spec)


@kopf.on.field(
    "PipelineRun", labels={"tekton.dev/pipeline": "crd-example-demo"}, field="status"
)
def update_pipelinerun_handler(old: Any, new: Any, body: Any, **_) -> None:
    """ """
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    conditions = new.get("conditions", [])
    conditions = [x for x in conditions if x["type"].lower() == SUCCEEDED]

    # Figure out the status from the first succeeded condition, if it exists.
    if not conditions:
        return

    condition_reason = conditions[0]["reason"].lower()

    if condition_reason.lower() == SUCCEEDED:
        signing_request_name = body["metadata"]["annotations"]["SigningRequest.name"]
        print("PIPELINE passed for signing request: {signing_request_name}")
        update_request_status(signing_request_name, "complete")
    elif condition_reason.lower() == FAILED:
        print("PIPELINE failed...")
        update_request_status(signing_request_name, "failed")


# @kopf.on.create('PipelineRun', labels={"tekton.dev/pipeline": "crd-example-demo"})
# def create_fn(spec, name, meta, status, **kwargs):
#     print(f"A new signing pipeline has been created {name} with spec: {spec}")

# @kopf.on.delete('PipelineRun')
# def delete_fn(spec, name, meta, status, **kwargs):
#     print(f"A new signing pipeline has been updated {name} with spec: {spec}, {meta}, {status}")
