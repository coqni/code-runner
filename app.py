# Flask + Dagger.io Code Runner
# This app allows running isolated code snippets using containerized execution, tracking metrics and exposing a simple API.

from flask import Flask, request, jsonify
import os
import uuid
import dagger
import asyncio
import time
import json
from threading import Lock
from load_dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
from flasgger import Swagger

load_dotenv()

# Initialize Flask app and Swagger documentation
app = Flask(__name__)
swagger = Swagger(app, config={
    'headers': [],
    'specs': [
        {
            'endpoint': 'apispec_1',
            'route': '/swagger/apispec_1.json',
            'rule_filter': lambda rule: True,
            'model_filter': lambda tag: True,
        }
    ],
    'static_url_path': '/swagger/flasgger_static',
    'swagger_ui': True,
    'specs_route': '/swagger/'
})

LANGUAGE = os.getenv("CODE_LANGUAGE", "python")
API_TOKEN = os.getenv("API_TOKEN", "my-default-token")
LOG_DIR = "logs"

LANGUAGE_CONFIG = {
    "python": {"image": "python:3.11", "cmd": ["python", "main.py"]},
    "java": {"image": "openjdk:17", "cmd": ["java", "Main.java"]},
    "javascript": {"image": "node:20", "cmd": ["node", "main.js"]},
}

results = {}
metrics = {
    "in_progress": 0,
    "total_executions": 0,
    "successful_executions": 0,
    "failed_executions": 0,
    "execution_times": {},
    "executions_by_language": {},
    "errors": {},
    "last_execution": None,
    "max_execution_time": 0.0,
    "avg_execution_time": 0.0
}
metrics_lock = Lock()

Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

def log_event(event):
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_path = Path(LOG_DIR) / f"{date_str}.log"
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")

# Verify if the x-api-key header matches the configured API token.
# Fails if the token is missing or incorrect.
def check_auth(request):
    token = request.headers.get("x-api-key")
    return token == API_TOKEN

@app.before_request
# Middleware to enforce API key protection for sensitive endpoints.
# Returns 401 if the x-api-key is missing or invalid.
def require_api_token():
    if request.endpoint in ["run_code", "get_result"] and not check_auth(request):
        return jsonify({"error": "Unauthorized"}), 401

async def execute_code(code, inputs, exec_id):
    config = LANGUAGE_CONFIG.get(LANGUAGE)
    # Fails if the selected language is unsupported
    if not config:
        results[exec_id] = f"Unsupported language: {LANGUAGE}"
        return

    with metrics_lock:
        metrics["in_progress"] += 1
        metrics["total_executions"] += 1
        metrics["executions_by_language"].setdefault(LANGUAGE, 0)
        metrics["executions_by_language"][LANGUAGE] += 1
        start_time = time.time()
        metrics["last_execution"] = datetime.utcnow().isoformat()

    try:
        async with dagger.Connection() as client:
            # Language-specific helper file expected to call user code per input
            # TODO: make variable per language
            helper_file = f"runner.py"
            main_file = f"main.py"
main_content = code

# Embed Python user code into a wrapper template for consistent function call
if LANGUAGE == "python":
    indented_code = "
".join(f"    {line}" for line in code.splitlines())
    main_content = f"def solve(input_str):
{indented_code}
"

src_dir = client.host().directory({
    main_file: main_content,
                helper_file: open(f"runners/{helper_file}").read(),
                "inputs.json": json.dumps(inputs)
            })

            container = (
                client.container()
                .from_(config["image"])
                .with_mounted_directory("/src", src_dir)
                .with_workdir("/src")
                .with_exec(config["cmd"], stdout=True, stderr=True)
            )

            try:
                stdout = await container.stdout()
                output_map = json.loads(stdout)
                results[exec_id] = {
                    k: (v if isinstance(v, dict) else {"output": v})
                    for k, v in output_map.items()
                }
                status = "success"
                with metrics_lock:
                    metrics["successful_executions"] += 1
            # Fails if code execution fails (e.g. runtime error)
            except Exception as e:
                results[exec_id] = {"error": str(e)}
                status = "error"
                with metrics_lock:
                    metrics["failed_executions"] += 1
                    error_type = type(e).__name__
                    metrics["errors"].setdefault(error_type, 0)
                    metrics["errors"][error_type] += 1
    # Fails if the entire container setup or execution logic breaks
    except Exception as e:
        results[exec_id] = {"error": str(e)}
        status = "error"
        with metrics_lock:
            metrics["failed_executions"] += 1
            error_type = type(e).__name__
            metrics["errors"].setdefault(error_type, 0)
            metrics["errors"][error_type] += 1
    finally:
        end_time = time.time()
        duration = end_time - start_time
        with metrics_lock:
            metrics["in_progress"] -= 1
            metrics["execution_times"][exec_id] = duration
            metric_values = list(metrics["execution_times"].values())
            metrics["max_execution_time"] = max(metric_values, default=0.0)
            metrics["avg_execution_time"] = sum(metric_values) / len(metric_values)

        log_event({
            "exec_id": exec_id,
            "language": LANGUAGE,
            "status": status,
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat()
        })

@app.route("/run", methods=["POST"])
def run_code():
    """
    Starts the execution of submitted code for a list of input strings.

    Request JSON:
    {
        "code": "<source code as string>",
        "inputs": ["input1", "input2", ...]
    }

    Returns:
    200 JSON:
    {
        "exec_id": "<execution ID>",
        "status": "started"
    }
    """
    data = request.json
    code = data.get("code")
    inputs = data.get("inputs", [])

    exec_id = str(uuid.uuid4())
    asyncio.create_task(execute_code(code, inputs, exec_id))

    return jsonify({"exec_id": exec_id, "status": "started"})

@app.route("/result/<exec_id>", methods=["GET"])
'''
JSON result format for /result/<exec_id>:
{
  "output": {
    "<input1>": {"output": "<stdout result>", "error": "<optional error string>"},
    "<input2>": {"output": "<stdout result>"},
    ...
  },
  "execution_time": <duration in seconds>
}

Example:
{
  "output": {
    "5": {"output": "25
"},
    "x": {"output": "", "error": "ValueError: invalid literal for int()..."}
  },
  "execution_time": 1.245
}
'''

def get_result(exec_id):
    """
    Retrieves the output for a specific execution ID.

    Returns:
    200 JSON (if complete):
    {
        "output": {
            "<input1>": {"output": "<stdout result>", "error": "<optional error>"},
            ...
        },
        "execution_time": <float>
    }

    202 JSON (if still running):
    {
        "status": "pending"
    }
    """
    if exec_id in results:
        exec_time = metrics["execution_times"].get(exec_id, None)
        return jsonify({"output": results[exec_id], "execution_time": exec_time})
    # Fails if the requested exec_id has not completed yet
    return jsonify({"status": "pending"}), 202

@app.route("/metrics", methods=["GET"])
def get_metrics():
    """
    Returns current state metrics for the code runner.

    Returns:
    200 JSON:
    {
        "in_progress": <int>,
        "total_executions": <int>,
        "successful_executions": <int>,
        "failed_executions": <int>,
        "execution_times": {"<exec_id>": <float>},
        "executions_by_language": {"python": <int>, ...},
        "errors": {"ErrorType": <int>},
        "last_execution": <ISO timestamp>,
        "max_execution_time": <float>,
        "avg_execution_time": <float>
    }
    """
    with metrics_lock:
        return jsonify(metrics)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
