"""Send a ComfyUI workflow to a Vast serverless endpoint.

The worker proxies ``/generate/sync`` to ai-dock's comfyui-api-wrapper.
Pass input images as URLs inside the workflow JSON; the wrapper downloads
them. When S3 is configured (env on the worker, or ``--s3`` here), the
response ``output`` entries include a ``url``.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid

from vastai import Serverless

ENDPOINT_NAME = "my-comfyui-endpoint"
COST = 100

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
log = logging.getLogger(__name__)


def s3_from_env() -> dict | None:
    """Build a per-request S3 override from the standard env vars."""
    access_key_id = os.getenv("S3_ACCESS_KEY_ID")
    secret_access_key = os.getenv("S3_SECRET_ACCESS_KEY")
    bucket_name = os.getenv("S3_BUCKET_NAME")
    if not all([access_key_id, secret_access_key, bucket_name]):
        return None

    s3 = {
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
        "bucket_name": bucket_name,
    }
    if endpoint_url := os.getenv("S3_ENDPOINT_URL"):
        s3["endpoint_url"] = endpoint_url
    if region := os.getenv("S3_REGION"):
        s3["region"] = region
    return s3


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send a ComfyUI workflow JSON to a Vast serverless endpoint"
    )
    parser.add_argument(
        "--endpoint",
        default=ENDPOINT_NAME,
        help=f"Vast endpoint name (default: {ENDPOINT_NAME})",
    )
    parser.add_argument(
        "--workflow",
        required=True,
        metavar="FILE",
        help="Path to a ComfyUI API-format workflow JSON",
    )
    parser.add_argument(
        "--s3",
        action="store_true",
        help=(
            "Attach per-request S3 config from S3_ACCESS_KEY_ID, "
            "S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME, and optional "
            "S3_ENDPOINT_URL / S3_REGION"
        ),
    )
    return parser


async def main_async() -> None:
    args = build_arg_parser().parse_args()

    with open(args.workflow) as f:
        workflow_json = json.load(f)

    payload_input = {
        "request_id": str(uuid.uuid4()),
        "workflow_json": workflow_json,
    }
    if args.s3:
        s3 = s3_from_env()
        if s3 is None:
            log.error(
                "S3 env vars are incomplete. Required: "
                "S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME"
            )
            sys.exit(1)
        payload_input["s3"] = s3

    payload = {"input": payload_input}

    try:
        async with Serverless() as client:
            endpoint = await client.get_endpoint(name=args.endpoint)
            response = await endpoint.request("/generate/sync", payload, cost=COST)
    except AttributeError as e:
        if "API key" in str(e):
            log.error("API key missing. Set VAST_API_KEY environment variable.")
        else:
            log.error("Error: %s", e)
        sys.exit(1)

    body = response.get("response", response) if isinstance(response, dict) else response
    outputs = body.get("output") if isinstance(body, dict) else None
    if not outputs:
        print(json.dumps(response, indent=2, default=str))
        return

    for item in outputs:
        url = item.get("url") if isinstance(item, dict) else None
        if url:
            print(url)
        else:
            print(json.dumps(item, default=str))


if __name__ == "__main__":
    asyncio.run(main_async())
