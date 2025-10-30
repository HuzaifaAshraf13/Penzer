import asyncio
import logging
from typing import Tuple

logger = logging.getLogger("penzer.tools")

class ToolsRunner:
    """Executes commands asynchronously for AI agent."""
    def __init__(self, config=None):
        self.config = config

    async def run(self, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return -1, "", "timeout"
        except Exception as e:
            logger.exception("ToolsRunner failed: %s", e)
            return -1, "", str(e)

    async def close(self):
        pass
