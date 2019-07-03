import time

from django.conf import settings
from kubernetes.client import Configuration as kubeconfig
from kubernetes.client import CoreV1Api as v1_kube_api
from kubernetes.client import ApiClient as kube_api_client

from awx.main.utils.common import parse_yaml_or_json
from awx.main.utils import (
    create_temporary_fifo,
)


class PodManager(object):

    def __init__(self, task):
        self.task = task
        self.credential = task.instance_group.credential
        self.kube_api = self._kube_api_connection(self.credential)
        self.pod_name = f"job-{task.id}"
        self.pod_definition = self._pod_definition()

    def deploy_pod(self):
        if not self.credential.kubernetes:
            raise RuntimeError('Pod deployment cannot occur without a Kubernetes credential')

        self.kube_api.create_namespaced_pod(body=self.pod_definition,
                                            namespace=self.namespace)

        while True:
            pod = self.kube_api.read_namespaced_pod(name=self.pod_name,
                                                    namespace=self.namespace)
            if pod.status.phase != 'Pending':
                break
            time.sleep(1)

        return pod

    def delete_pod(self):
        return self.kube_api.delete_namespaced_pod(name=self.pod_name,
                                                   namespace=self.namespace)

    @property
    def namespace(self):
        return self.pod_definition['metadata']['namespace']

    def _kube_api_connection(self, credential):
        configuration = kubeconfig()
        configuration.api_key["authorization"] = credential.get_input('bearer_token')
        configuration.api_key_prefix['authorization'] = 'Bearer'
        configuration.host = credential.get_input('host')

        if credential.get_input('verify_ssl'):
            ca_cert_data = credential.get_input('ssl_ca_cert')
            configuration.ssl_ca_cert = create_temporary_fifo(ca_cert_data.encode())
        else:
            configuration.verify_ssl = False

        return v1_kube_api(kube_api_client(configuration))

    def _pod_definition(self):
        default_pod_spec = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": self.pod_name,
                "namespace": settings.AWX_CONTAINER_GROUP_DEFAULT_NAMESPACE
            },
            "spec": {
                "containers": [{
                    "name": self.pod_name,
                    "image": settings.AWX_CONTAINER_GROUP_DEFAULT_IMAGE,
                    "tty": True,
                    "stdin": True,
                    "imagePullPolicy": "Always",
                    "args": [
                        'sleep', 'infinity'
                    ]
                }]
            }
        }

        if self.task.instance_group.pod_spec_override:
            pod_spec_override = parse_yaml_or_json(
                self.task.instance_group.pod_spec_override)

            return {**default_pod_spec, **pod_spec_override}

        return default_pod_spec
