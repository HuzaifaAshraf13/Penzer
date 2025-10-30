````{"id":"56021","variant":"standard","title":"AGENT_MAIN.md — Penzer Agent Orchestrator Design"}
# AGENT_MAIN.md  
## Penzer Agent — Core Orchestrator Design Document  

---

### **Purpose**
The `Agent/main.py` file acts as the **central orchestrator** for the Penzer AI Agent.  
It manages initialization, coordination between internal subsystems (Planner, Memory, Tools, Parser, Search), and ensures safe, explainable, and human-supervised operation.  
This is the brainstem of the agent — the execution and communication backbone.

---

## **1. Overview**

### Responsibilities
- Boot and initialize core modules (`planner`, `memory`, `tools`, `parser`, `search`, `config`).  
- Load configuration, LLM credentials, and startup environment.  
- Manage the lifecycle of an operation: **input → plan → execute → parse → verify → store**.  
- Enforce **human-in-loop** controls for risky or destructive operations.  
- Maintain a consistent, auditable context for each operation (via `context.json`).  
- Log all actions, results, and errors in structured form.  
- Handle fail-safes, retries, and controlled shutdowns.  

### Core Workflow
1. Initialize environment & config.  
2. Connect to selected LLM via `config/config.py`.  
3. Create or load current `context.json`.  
4. Receive user command or task.  
5. Pass input to `planner` for decomposition into actionable steps.  
6. Execute planned steps via `tools`.  
7. Parse results using `parser`.  
8. Verify and cross-check results with `search` and prior memory.  
9. Store all verified data in `memory` (FAISS + journal).  
10. Present verified report or await human approval for next step.

---

## **2. Initialization Phase**

### Steps
1. **Display Boot Screen (optional)**  
   Use the `PENZER_DIAGRAM` animation (from main CLI) to indicate system startup.
2. **Load Configuration**  
   Import from `config/config.py` (connect LLM + tool settings).  
   Validate model credentials, FAISS path, and prompt directory.
3. **Initialize Subsystems**
   - `Memory`: connect to FAISS and open journaling layer.  
   - `Planner`: initialize LLM client, load prompt templates.  
   - `Parser`: load schema definitions.  
   - `Tools`: register available tools and validate paths.  
   - `Search`: verify network and API access.  
4. **Load or Create `context.json`**
   - Contains active session details: `operation_id`, `user`, `selected_model`, `start_time`, and `state`.

### Example Context Layout
```json
{
  "operation_id": "recon_2025_10_30_001",
  "status": "initialized",
  "user": "operator",
  "selected_model": "gemini-2.0",
  "memory_index": "faiss_index_v1",
  "tools": ["nmap", "whois"],
  "last_action": null,
  "logs": []
}
```

---

## **3. Task Lifecycle**

### A. Receive Task
- Input can come from CLI (`penzer run`) or system message queue.  
- Each task is wrapped in a `Task` object:
```python
Task(id, description, risk_level, user_query, status, created_at)
```

### B. Plan Phase
- Pass `Task.description` to `Planner.plan_task()`.
- Planner uses LLM + stored prompts to generate sequence:
```json
{
  "steps": [
    {"id": 1, "action": "run_tool", "tool": "nmap", "target": "192.168.0.0/24"},
    {"id": 2, "action": "parse_output", "depends_on": 1},
    {"id": 3, "action": "analyze_results", "depends_on": 2}
  ]
}
```
- Each plan step is verified via the verifier LLM to avoid hallucinations.

### C. Execution Phase
- The orchestrator dispatches each step to the `Tools` module.
- Capture raw outputs, timestamps, and any errors.
- Sandbox tool executions; log and retry transient failures.

### D. Parsing Phase
- Send raw tool output to `Parser.parse_output()`.
- Ensure parser follows schema and passes validation.
- Invalid JSON triggers re-run with adjusted prompt (up to 3 retries).

### E. Verification Phase
- Send parsed results to `Search` for external validation (CVE data, exploit DBs, etc.).
- Cross-check with prior memory embeddings for contradictions.
- If verified → mark `status=trusted`; else → request human review.

### F. Storage Phase
- Store validated JSON + embeddings in `Memory`.
- Append operation summary to `journal/` with provenance metadata:
```json
{
  "source": "nmap",
  "verified": true,
  "confidence": 0.94,
  "operation_id": "recon_2025_10_30_001",
  "timestamp": "2025-10-30T21:42:00Z"
}
```

### G. Reporting & Shutdown
- Generate final report (JSON + human-readable summary).
- Offer human approval for next action or termination.
- Update context to `status: completed` and close subsystems cleanly.

---

## **4. Safety & Human Oversight**

### Human-in-Loop Logic
- **Risk Levels:**  
  1–2 → auto-run  
  3–4 → requires one approval  
  5+ → requires dual approval  
- Critical commands (e.g., exploit launch) always require manual confirmation.
- Approvals stored in `journal/approvals/<task_id>.json`.

### Anti-Hallucination Loop
- Every LLM-generated plan or parser output must:
  1. Match JSON schema.  
  2. Pass verifier consistency check.  
  3. Align with tool output or search results.  
  4. Be flagged if confidence < threshold.

If any fail, orchestrator reruns the reasoning step with contextual feedback until fixed or manually overridden.

---

## **5. Logging & Observability**

### Structured Logging
- JSON-based logs written to `logs/penzer.log`.
- Fields: `timestamp, module, action, user, task_id, status, latency, confidence`.

### Metrics
- `/metrics` endpoint exposes:
  - `tasks_processed_total`
  - `llm_latency_seconds`
  - `faiss_index_size`
  - `tool_exec_duration_seconds`
  - `task_failure_total`

### Alerts
- On repeated verification failures or LLM timeouts → send Slack/email alert.
- On missing FAISS index or config file → trigger self-repair suggestion.

---

## **6. Error Handling**

| Error Type | Description | Action |
|-------------|--------------|--------|
| ConfigError | Missing or invalid config | Halt + prompt setup |
| ToolError | Tool not found or crashed | Log, retry 2x, mark failed |
| ParseError | Parser output invalid | Retry 3x, escalate |
| LLMError | API error or invalid JSON | Reconnect, retry |
| MemoryError | FAISS or journal write failure | Fallback to temp file |
| VerificationError | Result unverified | Flag and request human review |

---

## **7. Integration Interfaces**

### Planner Interface
```python
plan = planner.plan_task(task)
```

### Tools Interface
```python
result = tools.run_command(plan_step)
```

### Parser Interface
```python
parsed = parser.parse_output(result)
```

### Memory Interface
```python
memory.store_result(parsed, operation_id)
```

### Search Interface
```python
verified = search.validate(parsed)
```

---

## **8. Config and Environment Integration**

- The orchestrator imports `config/config.py` to access environment variables:
  - `SELECTED_MODEL`, `API_KEYS`, `LLM_RETRY_MAX`, `RATE_LIMITS`, `PROMPT_DIR`
- The `configure.py` CLI lets user:
  - Add new LLM keys  
  - Select model (Gemini / OpenAI / Claude / Localhost)  
  - Set default behavior (auto verify, manual approval, etc.)

---

## **9. Extensibility**

- The orchestrator supports a **plugin discovery mechanism**:
  - Load `penzer/plugins/<plugin_name>/` dynamically on startup.
  - Each plugin can register new tools, parsers, or search adapters.

---

## **10. Safety Summary**

- **LLM Temperature:** ≤ 0.3 for reasoning tasks.  
- **Execution Policy:** sandbox, non-destructive by default.  
- **Verification Required:** before committing to memory.  
- **Logging:** all steps signed and timestamped.  
- **Consent Enforcement:** cannot execute unless `consent.json` present.

---

## **11. Future Upgrades**

- Multi-agent orchestration (collaborative agents).  
- Real-time streaming analysis dashboard.  
- Policy-based self-healing (auto replan).  
- Threat intelligence integration (via `search.py`).  
- Context persistence between user sessions.

---

### **Conclusion**
`Agent/main.py` is the **control center** of Penzer — it ties together reasoning, execution, verification, and memory.  
It ensures all modules interact safely, logically, and verifiably, under strict human supervision when required.  
This file defines the behavior loop that makes Penzer a true **AI-driven offensive recon assistant** — intelligent, traceable, and grounded.
````
