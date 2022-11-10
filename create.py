import yaml
from kubernetes import config
from openshift.dynamic import DynamicClient
import random
import os

NAMESPACE = os.environ.get("CRD_DEMO_NAMESPACE", "default")


def main():
    k8s_client = config.new_client_from_config()
    dyn_client = DynamicClient(k8s_client)

    v1_services = dyn_client.resources.get(api_version="v1", kind="SigningRequest")
    crd_id = random.randint(10, 10000000)
    service = f"""

    apiVersion: redhat.com/v1
    kind: SigningRequest
    metadata:
      name: my-signing-request-instance-{crd_id}
      annotations:
        status: "started"
    spec:
      pull_spec: quay.io/araszka/test:latest
      requestor: araszka
    """

    service_data = yaml.load(service)
    resp = v1_services.create(body=service_data, namespace=NAMESPACE)

    # resp is a ResourceInstance object
    print(resp.metadata)


if __name__ == "__main__":
    main()
