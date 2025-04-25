# Code Runner

### Archtecture

```mermaid
graph TD
    subgraph User Interface
        UI[Coqni UI]
    end

    subgraph Platform
        EP[Educational Platform]
    end

    subgraph Code Execution Backend
        CR[CodeRunner API]
        DAG[Dagger Engine]
        C1[Dagger Container Python]
        C2[Dagger Container Java]
        C3[...]
        METRICS[Metrics Store]
        LOGS[Log File /logs/YYYY-MM-DD.log]
    end

    %% Communication Flows
    UI --> EP
    EP --> CR
    CR --> DAG
    DAG --> C1
    DAG --> C2
    DAG --> C3
    CR --> METRICS
    CR --> LOGS
```

### Data Flow

```mermaid
sequenceDiagram
    participant EducationalPlatform
    participant CodeRunnerAPI
    participant DaggerContainer1 as DaggerContainer (Submission 1)
    participant DaggerContainer2 as DaggerContainer (Submission 2)
    participant MetricsStore
    participant LogFile

    %% Submission 1
    EducationalPlatform->>+CodeRunnerAPI: POST /run (code + inputs)
    CodeRunnerAPI->>+MetricsStore: increment in_progress, total_executions
    CodeRunnerAPI->>+DaggerContainer1: run all inputs for Submission 1
    DaggerContainer1-->>-CodeRunnerAPI: { input: { output, error? }, ... }
    CodeRunnerAPI->>+MetricsStore: update stats (duration, success/failure)
    CodeRunnerAPI->>+LogFile: write to /logs/YYYY-MM-DD.log

    %% Submission 2
    EducationalPlatform->>+CodeRunnerAPI: POST /run (code + inputs)
    CodeRunnerAPI->>+MetricsStore: increment in_progress, total_executions
    CodeRunnerAPI->>+DaggerContainer2: run all inputs for Submission 2
    DaggerContainer2-->>-CodeRunnerAPI: { input: { output, error? }, ... }
    CodeRunnerAPI->>+MetricsStore: update stats (duration, success/failure)
    CodeRunnerAPI->>+LogFile: write to /logs/YYYY-MM-DD.log

    %% Polling results
    EducationalPlatform->>+CodeRunnerAPI: GET /result/<exec_id>
    CodeRunnerAPI-->>-EducationalPlatform: result JSON (output + execution_time)

    %% Metrics retrieval
    EducationalPlatform->>+CodeRunnerAPI: GET /metrics
    CodeRunnerAPI-->>-EducationalPlatform: stats JSON
```

---

### ✅ Requirements

1. **Python ≥ 3.10**
   - Dagger requires `async` and `await`, supported from Python 3.7, but ≥3.10 is recommended.
   - Check:
     ```bash
     python --version
     ```

2. **[Dagger CLI & Engine](https://docs.dagger.io/install/):**
   - Install:
     ```bash
     brew install dagger/tap/dagger  # macOS
     # or via install script:
     curl -L https://dl.dagger.io/dagger/install.sh | sh
     ```
   - Test:
     ```bash
     dagger version
     ```

3. **Docker (for container execution)**
   - Dagger uses Docker internally, so Docker must be running:
     ```bash
     docker version
     ```

4. **Python dependencies**
   - Install with `pip`:
     ```bash
     pip install flask flasgger dagger-io
     ```

---

### 📂 Local Project Structure (Example)

```
.
├── app.py                  # your main code runner (Flask)
├── runners/
│   └── runner.py           # language-specific runner for Python
├── logs/                   # created automatically
```

---

### ⚙️ Environment Variables

Set before starting:

```bash
export CODE_LANGUAGE=python
export API_TOKEN=mysecrettoken
```

---

### 🚀 Run

```bash
python app.py
```

Then open Swagger:
```
http://localhost:5000/swagger/index.html
```

---

### 📡 Example Call via `curl`

```bash
curl -X POST http://localhost:5000/run \
  -H "Content-Type: application/json" \
  -H "x-api-key: mysecrettoken" \
  -d '{
    "code": "return str(int(input_str) * int(input_str))",
    "inputs": ["4", "x"]
}'
```

Then:
```bash
curl -H "x-api-key: mysecrettoken" http://localhost:5000/result/<exec_id>
```
