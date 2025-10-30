# Planner Prompt

Goal: convert a user `Task` description into a deterministic, auditable plan of steps. The plan is consumed by the orchestrator and must be valid JSON matching the schema shown below.

Required output format (JSON):

{
	"task_id": "<string>",
	"summary": "<human readable summary>",
	"steps": [
		{
			"id": 1,
			"action": "run_tool",                // one of: run_tool, parse_output, analyze_results, human_review, store_memory
			"tool": "nmap",                      // optional; required for run_tool
			"command": "nmap -sS 192.168.0.0/24", // command to run (for run_tool)
			"depends_on": null,                   // integer id of step this depends on
			"risk_level": 3,                      // integer 1-5 (1 low, 5 high)
			"timeout_seconds": 120
		}
	],
	"confidence": 0.0-1.0
}

Planner rules and guidance:
- Keep step count reasonably small (prefer decomposition into 3–12 actions). If the task is very large, produce a top-level decomposition and mark follow-up tasks.
- Assign `risk_level` based on tool and action. Use conservative defaults: network enumeration tools (nmap, masscan) → 3; passive queries (whois, nslookup) → 1; destructive actions (exploit, write system files) → 5.
- Always include `depends_on` when a step consumes another step's output. This enables the orchestrator to sequence execution.
- For any `run_tool` step include an explicit `command` string and `timeout_seconds`.
- Provide a compact `summary` explaining overall plan and critical risks.

Validation hints (planner should produce valid JSON):
- Ensure all step `id` values are unique integers starting at 1.
- Ensure required fields (`action`, and `command` for `run_tool`) are present.
- Provide an overall `confidence` score and a short `explain` field if `confidence` < 0.6 explaining what uncertainties exist.

Example plan (short):

{
	"task_id": "recon_2025_10_30_001",
	"summary": "Scan target network for open ports, parse results, and analyze services.",
	"steps": [
		{"id": 1, "action": "run_tool", "tool": "nmap", "command": "nmap -sV 192.168.0.0/24", "depends_on": null, "risk_level": 3, "timeout_seconds": 300},
		{"id": 2, "action": "parse_output", "tool": "parser", "depends_on": 1, "risk_level": 1},
		{"id": 3, "action": "analyze_results", "tool": "analyzer", "depends_on": 2, "risk_level": 1}
	],
	"confidence": 0.85
}

If the planner cannot make a safe plan (e.g., insufficient target info), return a `clarify` instruction instead of a plan:

{
	"clarify": "I need a target IP range or hostname to continue."
}
