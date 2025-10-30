import json
import re
from typing import Dict, Any, Tuple

class Parser:
    """Converts raw tool outputs into JSON/dict format."""
    def parse(self, raw: Tuple[int, str, str]) -> Dict[str, Any]:
        exitcode, stdout, stderr = raw
        parsed: Dict[str, Any] = {
            "exitcode": exitcode,
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
            "structured": {}
        }

        # Example: parse nmap-style open ports
        open_ports = re.findall(r"(\d+)/tcp\s+open\s+(\S+)", stdout)
        if open_ports:
            parsed["structured"]["open_ports"] = [
                {"port": int(port), "service": service} for port, service in open_ports
            ]

        # If stdout is already JSON, parse it
        try:
            j = json.loads(stdout)
            parsed["structured"] = j
        except Exception:
            pass

        return parsed
