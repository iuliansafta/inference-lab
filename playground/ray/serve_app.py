# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["ray[serve]==2.59.0"]
# ///
import asyncio
import os
import time

from ray import serve
from ray.serve.handle import DeploymentHandle
from starlette.requests import Request

SECONDS_PER_TOKEN = 0.02
SLOTS_PER_REPLICA = 4


@serve.deployment(max_ongoing_requests=SLOTS_PER_REPLICA, ray_actor_options={"num_cpus": 0.5})
class FakeModel:
    async def generate(self, tokens: int) -> dict:
        await asyncio.sleep(tokens * SECONDS_PER_TOKEN)
        return {"replica": serve.get_replica_context().replica_id.unique_id}


@serve.deployment(max_ongoing_requests=1000)
class Gateway:
    def __init__(self, model: DeploymentHandle) -> None:
        self.model = model

    async def __call__(self, request: Request) -> dict:
        tokens = int(request.query_params.get("tokens", "50"))
        start = time.monotonic()
        result = await self.model.generate.remote(tokens)
        return result | {"model_ms": round((time.monotonic() - start) * 1000)}


def model_options() -> dict:
    replicas = os.environ.get("REPLICAS", "2")
    if replicas != "auto":
        return {"num_replicas": int(replicas)}
    return {
        "num_replicas": "auto",
        "autoscaling_config": {
            "min_replicas": 1,
            "max_replicas": 4,
            "target_ongoing_requests": 2,
            "upscale_delay_s": 3,
            "downscale_delay_s": 30,
        },
    }


app = Gateway.bind(FakeModel.options(**model_options()).bind())

if __name__ == "__main__":
    print("Serving on http://127.0.0.1:8000/?tokens=50  Dashboard: http://127.0.0.1:8265/#/serve  Ctrl+C to stop.")
    serve.run(app, blocking=True)
