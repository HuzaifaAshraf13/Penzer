# main.py (global entrypoint with Penzer awaken sequence)
import asyncio
import logging
import os
import random
import time
from typing import Optional

from colorama import Fore, Style, init as colorama_init

# initialize colorama for cross-platform color support
colorama_init(autoreset=True)

# optional: import your Agent factory
from Agent.main import Agent

logger = logging.getLogger("penzer")
logging.basicConfig(level=logging.INFO)


PENZER_DIAGRAM = f"""{Fore.RED + Style.BRIGHT}
$ penzer
  _____  ______ _   _ ____________ _____  
 |  __ \\|  ____| \\ | |___  /  ____|  __ \\ 
 | |__) | |__  |  \\| |  / /| |__  | |__) |
 |  ___/|  __| | . ` | / / |  __| |  _  / 
 | |    | |____| |\\  |/ /__| |____| | \\ \\ 
 |_|    |______|_| \\_/_____|______|_|  \\_\\
                                 
    [ Penzer - Offensive Recon ]

{Style.RESET_ALL}"""


def penzer_awaken_sequence() -> None:
    """Blocking awaken sequence (call before starting asyncio loop)."""
    os.system("cls" if os.name == "nt" else "clear")
    print(PENZER_DIAGRAM)
    time.sleep(0.8)
    print(Fore.WHITE + "[ OK ] Initializing modules......")
    time.sleep(0.6)
    print(Fore.WHITE + "[[ .. ] Loading AI client...")
    time.sleep(0.6)
    print(Fore.WHITE + "[BOOT] PENZER is now active...")
    time.sleep(0.8)
    print(Fore.RED + "\n[ Penzer Awakened ]")
    print(Fore.RED + "» Operation: Offensive Recon")
    print(Fore.RED + "» Status: LIVE\n")
    time.sleep(0.6)
    print(Fore.RED + random.choice([
        "» No firewalls can stop what's coming.",
        "» You gave me root. I gave you silence.",
        "» Exploits don't knock — they enter.",
        "» Penzer doesn't scan. It hunts.",
        "» Penzer Break it to save it.",
    ]))
    time.sleep(0.5)


async def async_penzer_awaken_sequence() -> None:
    """Non-blocking awaken sequence usable inside asyncio (uses asyncio.sleep)."""
    # clear can be blocking; keep it sync but short
    os.system("cls" if os.name == "nt" else "clear")
    print(PENZER_DIAGRAM)
    await asyncio.sleep(0.8)
    print(Fore.WHITE + "[ OK ] Initializing modules......")
    await asyncio.sleep(0.6)
    print(Fore.WHITE + "[[ .. ] Loading AI client...")
    await asyncio.sleep(0.6)
    print(Fore.WHITE + "[BOOT] PENZER is now active...")
    await asyncio.sleep(0.8)
    print(Fore.RED + "\n[ Penzer Awakened ]")
    print(Fore.RED + "» Operation: Offensive Recon")
    print(Fore.RED + "» Status: LIVE\n")
    await asyncio.sleep(0.6)
    print(Fore.RED + random.choice([
        "» No firewalls can stop what's coming.",
        "» You gave me root. I gave you silence.",
        "» Exploits don't knock — they enter.",
        "» Penzer doesn't scan. It hunts.",
        "» Penzer Break it to save it.",
    ]))
    await asyncio.sleep(0.5)


async def main() -> None:
    """Main async entrypoint — creates and runs the Agent."""
    # If you prefer the non-blocking awake inside the loop, await it:
    # await async_penzer_awaken_sequence()

    # If you used the blocking penzer_awaken_sequence() already, skip the async call.
    agent = Agent.from_config()  # factory to inject config/backends
    try:
        await agent.run()
    except asyncio.CancelledError:
        logger.info("Shutdown requested")
    finally:
        await agent.close()


if __name__ == "__main__":
    # Option A: Run blocking awaken sequence, then start asyncio loop.
    penzer_awaken_sequence()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
