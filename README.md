# ComfyUI PyWorker

Vast serverless PyWorker for ComfyUI. `worker.py` is the official
[comfyui-json](https://github.com/vast-ai/pyworker/tree/main/workers/comfyui-json)
worker: it proxies `POST /generate/sync` to ai-dock's
[comfyui-api-wrapper](https://github.com/ai-dock/comfyui-api-wrapper) on
`127.0.0.1:18288`. The wrapper, shipped with the Vast ComfyUI template
image, submits the workflow to ComfyUI, waits for completion, collects
outputs, and uploads them to S3.

## Endpoint setup

Point the template at this repository:

| Variable | Required | Purpose |
| --- | --- | --- |
| `PYWORKER_REPO` | yes | Git URL of this repo. `start_server.sh` clones it and runs `python3 -m worker`. |
| `PYWORKER_REF` | no | Branch, tag, or commit to check out. |
| `S3_ACCESS_KEY_ID` | for uploads | S3 access key. |
| `S3_SECRET_ACCESS_KEY` | for uploads | S3 secret key. |
| `S3_BUCKET_NAME` | for uploads | Bucket that receives generated files. |
| `S3_ENDPOINT_URL` | no | S3-compatible endpoint. Defaults to AWS when unset. |
| `S3_REGION` | no | Region. |
| `BENCHMARK_JSON_PATH` | no | Workflow used for the warm-up benchmark. See below. |

Use the [ComfyUI (Serverless)](https://cloud.vast.ai/?ref_id=62897&creator_id=62897&name=ComfyUI%20(Serverless)) template so ComfyUI and the api-wrapper are already running.

## Request

`POST /generate/sync` with a ComfyUI API-format workflow. Input images are URLs inside the workflow. The wrapper downloads each URL into ComfyUI's `input/` directory and rewrites the node to the local filename.

```json
{
  "input": {
    "request_id": "optional-uuid",
    "workflow_json": {
      "10": {
        "class_type": "LoadImage",
        "inputs": { "image": "https://example.com/input.png" }
      }
    }
  }
}
```

`request_id` is optional; the wrapper mints one when it is omitted. A per-request `input.s3` object overrides the `S3_*` env vars for that call:

```json
"s3": {
  "access_key_id": "...",
  "secret_access_key": "...",
  "endpoint_url": "https://s3.amazonaws.com",
  "bucket_name": "your-bucket",
  "region": "us-east-1"
}
```

## Response

The wrapper returns a result envelope. Uploaded files appear in `output[].url`.

```json
{
  "id": "request-uuid",
  "status": "completed",
  "message": "Processing complete.",
  "output": [
    {
      "filename": "ComfyUI_00001_.png",
      "node_id": "9",
      "url": "https://your-bucket.s3.amazonaws.com/ComfyUI_00001_.png"
    }
  ],
  "timings": {
    "preprocess_ms": 12,
    "generation_ms": 18412,
    "postprocess_ms": 743
  }
}
```

Without S3 configured, files stay on the worker and `url` is omitted.

## Client

```bash
pip install -r requirements.txt
export VAST_API_KEY=<your_api_key>

python client.py --endpoint my-comfyui-endpoint --workflow workflow.json
```

`--s3` attaches `input.s3` from `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, and optional `S3_ENDPOINT_URL` / `S3_REGION`. The client prints each `output[].url`.

## Benchmark

On warm-up the worker sends one workflow so Vast can estimate capacity. The first readable file wins:

1. `misc/benchmark.json` in this repo
2. `$BENCHMARK_JSON_PATH`
3. `/opt/comfyui-api-wrapper/workflows/pyworker_benchmark.json` (symlink maintained by the Vast ComfyUI image)

If none of those exist, it falls back to an SD1.5 `Text2Image` job sized by `BENCHMARK_TEST_WIDTH` (512), `BENCHMARK_TEST_HEIGHT` (512), and `BENCHMARK_TEST_STEPS` (20), with a prompt from `misc/test_prompts.txt`.

`misc/benchmark.json.example` is a starting workflow. Copy it to `misc/benchmark.json` and replace seed fields with `__RANDOM_INT__`; the api-wrapper substitutes a fresh integer on each run.
