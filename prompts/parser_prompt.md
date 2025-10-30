# Parser Prompt

Purpose: Convert raw tool outputs (stdout/stderr) into validated JSON objects suitable for storage, verification, and downstream analysis.

Output requirements:
- Return a single JSON object with the fields:
	- `exitcode` (int)
	- `stdout` (string)
	- `stderr` (string)
	- `structured` (object) — the extracted structured data (e.g., open_ports, services, hostnames)
	- `errors` (optional array) — parsing errors or warnings
	- `provenance` (array) — list of sources/tool names and timestamps used to create the structured data

Parsing rules & tips:
- If the `stdout` is valid JSON, set `structured` to that JSON after basic schema checks.
- For common tools, extract these fields when present:
	- nmap: `open_ports` -> [{"port": int, "protocol": "tcp/udp", "service": "..."}], `scan_start`, `scan_end`.
	- whois: `registrant`, `created`, `expires`, `nameservers`.
	- curl/wget: `http_status`, `headers`, `body_snippet`.
- Normalize timestamps to ISO 8601 (UTC) when possible.
- Include raw evidence for any structured field (e.g., include the exact line from stdout that produced the `open_ports` entry) in `provenance`.

Error handling and retries:
- If parsing fails to produce valid JSON in `structured`, include an `errors` array describing issues.
- Provide suggested remediation text (e.g., "try running with -oX for XML output" or "increase timeout") when helpful.

Example output (nmap snippet):

{
	"exitcode": 0,
	"stdout": "...nmap output...",
	"stderr": "",
	"structured": {
		"open_ports": [{"port": 22, "protocol": "tcp", "service": "ssh"}, {"port": 80, "protocol": "tcp", "service": "http"}],
		"hosts": ["192.168.0.10"]
	},
	"provenance": [{"source": "nmap", "line": "22/tcp open ssh", "timestamp": "2025-10-30T21:42:00Z"}]
}

If you cannot recover structured data, return `structured: {}` and provide actionable errors in `errors` so the orchestrator can decide a retry with adjusted prompts.
