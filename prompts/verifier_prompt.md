# Verifier Prompt

Goal: Decide whether a parsed result is trustworthy, highlight contradictions, and propose follow-up checks when confidence is low.

Input: a parsed JSON object (from the Parser) along with raw tool outputs and any prior memory results relevant to the same `operation_id`.

Verifier output schema (JSON):

{
	"verified": true | false,
	"confidence": 0.0-1.0,
	"checks": [
		{"check": "schema_match", "status": "pass" | "fail", "details": "..."},
		{"check": "cross_check_memory", "status": "pass", "details": "similar previous findings: ..."}
	],
	"recommended_actions": ["search_cve:package_name", "human_review"],
	"notes": "short human readable summary"
}

Verification guidance:
- Check that required fields in `structured` are present and consistent with `stdout` evidence.
- Cross-check parsed artifacts against prior memory (embeddings or journals) for contradictions or duplicates.
- Optionally consult external sources (CVE DB, NVD, Shodan) to validate claims about service versions or known vulnerabilities — if external calls are required, return `recommended_actions` rather than making the calls yourself.

Confidence scoring hints (suggested, implementor can adapt):
- 0.0–0.4: low confidence — require human review or additional checks.
- 0.4–0.75: medium — consider secondary verification (search or rerun tool with different flags).
- 0.75–1.0: high — safe to store in memory automatically.

When verification fails or is inconclusive:
- Provide a list of deterministic follow-up checks (e.g., "re-run nmap with -sV on host X", "cross-check host X on Shodan").

Example response:

{
	"verified": false,
	"confidence": 0.43,
	"checks": [
		{"check": "schema_match", "status": "pass"},
		{"check": "cross_check_memory", "status": "fail", "details": "No prior entries found"}
	],
	"recommended_actions": ["re_run: nmap -sV 192.168.0.10", "human_review"],
	"notes": "Open ports found but version detection missing; recommend re-run with -sV before trusting service version data."
}
