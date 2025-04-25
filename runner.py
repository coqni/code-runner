# runner.py which calls "solve" in "main.py". A separate runner is required for each supported language.

import json
import sys
import traceback

# Load user inputs from file
with open("inputs.json", "r") as f:
    inputs = json.load(f)

# Import user code as a standard function from main.py
# main.py must define a function named `solve(input_str: str) -> str`
from main import solve

results = {}

for input_item in inputs:
    try:
        # Call the user's solve function with each input string
        output = solve(input_item)
        results[input_item] = {"output": str(output)}
    except Exception as e:
        # If the user's function raises an error, capture it
        results[input_item] = {
            "output": "",
            "error": "".join(traceback.format_exception_only(type(e), e)).strip()
        }

# Output results as JSON to stdout for the runner host to capture
print(json.dumps(results))
