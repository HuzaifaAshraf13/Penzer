# source env/bin/activate
import asyncio
import logging
import os
import json
from .memory import Memory
from .tools import ToolsRunner
from .parser import Parser
from .context import Context
from .prompts import load_prompt
import config.config as cfg

logger = logging.getLogger("penzer.agent")
logging.basicConfig(level=logging.INFO)


class Agent:
    def __init__(self, memory: Memory, tools: ToolsRunner, parser: Parser, ctx: Context, config: dict | None = None):
        self.memory = memory
        self.tools = tools
        self.parser = parser
        self.ctx = ctx
        self.config = config or {}
        self._stop = asyncio.Event()

    @classmethod
    def from_config(cls, config: dict | None = None):
        memory = Memory(config=config)
        tools = ToolsRunner(config=config)
        parser = Parser()
        ctx = Context()
        agent = cls(memory, tools, parser, ctx, config=config)
        # perform initial load of persisted context if present
        try:
            ctx.load_context()
        except Exception:
            # if load fails, continue with generated run_id
            pass
        return agent

    def initialize(self):
        """Synchronous initialization tasks (create dirs, write initial context)."""
        # ensure logs and journal directories exist
        os.makedirs("logs", exist_ok=True)
        os.makedirs("journal", exist_ok=True)

        # load selected model from config
        selected = None
        if self.config:
            selected = self.config.get("SELECTED_MODEL") or self.config.get("selected_model")
        if selected:
            self.ctx.update("selected_model", selected)

        # Load system prompt (externalized)
        try:
            system_prompt = load_prompt("system_prompt")
            if system_prompt:
                self.ctx.update("system_prompt", system_prompt)
                self.ctx.append_log("agent", "load_prompt", "info", {"prompt": "system_prompt"})
        except Exception:
            logger.exception("Failed to load system prompt")

        # persist initial context
        try:
            self.ctx.append_log("agent", "initialize", "info", {"selected_model": selected})
            self.ctx.save_context()
        except Exception:
            logger.exception("Failed to save initial context")

    async def run_once(self):
        task = await self.memory.get_next_task()
        if not task:
            await asyncio.sleep(1)
            return

        # Assess risk and require human approval for risky tasks
        risk = self._assess_risk(task.command)
        if risk >= 3:
            approved = await asyncio.to_thread(self._request_approval, task, risk)
            if not approved:
                # mark task as failed/blocked in memory
                await self.memory.store_result(task.id, json.dumps({"status": "blocked_by_human", "risk": risk}))
                self.ctx.append_log("agent", "task_blocked", "warn", {"task_id": task.id, "risk": risk})
                return

        raw_output = await self.tools.run(task.command)
        parsed = self.parser.parse(raw_output)

        # Store temp JSON in context
        self.ctx.store_temp_json(parsed)

        # Verification stub: in future call search.validate(parsed)
        verified = True

        result_payload = {
            "task_id": task.id,
            "command": task.command,
            "verified": verified,
            "risk": risk,
            "parsed": parsed,
        }

        # Save to memory permanently (store JSON string)
        try:
            await self.memory.store_result(task.id, json.dumps(result_payload))
        except Exception:
            logger.exception("Failed to store result for task %s", task.id)

        # Append journal entry
        try:
            journal_path = os.path.join("journal", f"{self.ctx.run_id}_task_{task.id}.json")
            with open(journal_path, "w", encoding="utf-8") as jf:
                json.dump(result_payload, jf, indent=2)
            self.ctx.append_log("agent", "task_completed", "info", {"task_id": task.id, "journal": journal_path})
            # persist context state
            self.ctx.save_context()
        except Exception:
            logger.exception("Failed to write journal for task %s", task.id)

        # Clear temp JSON
        self.ctx.clear_temp_json()

    async def run(self):
        # synchronous initialize prior to entering async loop
        try:
            self.initialize()
        except Exception:
            logger.exception("Initialization failed")

        while not self._stop.is_set():
            try:
                await self.run_once()
            except Exception as e:
                logger.exception("Error in run_once: %s", e)
                await asyncio.sleep(1)

    async def stop(self):
        self._stop.set()

    async def close(self):
        await self.tools.close()
        await self.memory.close()

    # ---- Helpers ----
    def _assess_risk(self, command: str) -> int:
        """Very small heuristic risk assessment: returns 1-5."""
        low_risk_keywords = ["ping", "curl", "wget", "whois", "nslookup"]
        med_risk_keywords = ["nmap", "masscan", "scan"]
        high_risk_keywords = ["exploit", "rm -rf", "shutdown", "reboot"]

        cmd = (command or "").lower()
        if any(k in cmd for k in high_risk_keywords):
            return 5
        if any(k in cmd for k in med_risk_keywords):
            return 3
        if any(k in cmd for k in low_risk_keywords):
            return 1
        return 2

    def _request_approval(self, task, risk: int) -> bool:
        """Blocking human approval prompt. Runs in a thread via asyncio.to_thread."""
        print(f"Task {task.id} requires approval (risk={risk}): {task.command}")
        resp = input("Approve? (y/N): ").strip().lower()
        return resp == "y"
