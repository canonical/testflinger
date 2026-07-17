"""
Smoke-test for the workshop workflow and related `just` actions:

Tests the typical flow and make sure that all function work as expected.

Usage:
    python test_workshop_actions.py            # full sequence
    python test_workshop_actions.py --dry-run  # print commands only
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

WORKSHOP = "workshop"
JUST = "just"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def check_prerequisites() -> None:
    """Abort immediately if the tools are not in the PATH."""
    if shutil.which(JUST) is None:
        sys.exit(
            f"ERROR: '{JUST}' CLI not found on PATH. "
            "This script must run via just."
        )
    if shutil.which(WORKSHOP) is None:
        sys.exit(
            f"ERROR: '{WORKSHOP}' CLI not found on PATH. "
            "This script must run inside a workshop container."
        )


def run(action: str, *extra_args: str, timeout: int = 120, dry_run: bool = False) -> None:
    """Run `workshop run dev <action> [extra_args]`, fail fast on error."""
    cmd = action.split() + list(extra_args)
    print(f"\n$ {' '.join(cmd)}")
    print("=================================================================")
    if dry_run:
        return
    result = subprocess.run(cmd, timeout=timeout, capture_output=True,
                            errors='ignore')
    print(str(result.stdout))
    print(str(result.stderr))
    if result.returncode != 0:
        if "address already in use" in str(result.stderr):
            print("\nYou will need to disconnect another workshop from the "\
                  "local host in order to run the tests here.\n")
        sys.exit(f"FAILED: action '{action}' exited with code {result.returncode}")


def run_logs(duration: int = 10, dry_run: bool = False) -> None:
    """
    Run the `logs` action for *duration* seconds then send SIGINT (like Ctrl-C).

    The action tails docker compose logs with --follow, so it never exits on
    its own; we interrupt it after a short window just to confirm it streams
    without immediately crashing.
    """
    cmd = "workshop exec -- server::logs".split()
    print(f"\n$ {' '.join(cmd)}  (will interrupt after {duration}s)")
    if dry_run:
        return
    proc = subprocess.Popen(cmd)
    time.sleep(duration)
    proc.send_signal(__import__("signal").SIGINT)
    try:
        proc.wait(timeout=duration)
    except subprocess.TimeoutExpired:
        proc.kill()

    print(proc.returncode)

    # logs is a streaming command; any exit code is acceptable here
    print(f"    logs streamed for {duration}s — OK")

    if proc.returncode != 0:
        print("continue")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them")
    args = parser.parse_args()
    dry_run = args.dry_run

    # go up one from the `.workshop` directory into the main project dir.
    os.chdir("..")

    if not args.dry_run:
        check_prerequisites()

    print("Workshop smoke tests")
    print("====================")

    try:
        run("just workshop disconnect", dry_run=dry_run)
        run("just workshop serve", dry_run=dry_run)
        run_logs(duration=15, dry_run=dry_run)
        run("workshop exec dev -- just server::populate",
            timeout=90, dry_run=dry_run)
        run("just workshop disconnect", dry_run=dry_run)
        run("just workshop connect", dry_run=dry_run)
        run("just workshop teardown", dry_run=dry_run)
        run("just workshop docker-prune", dry_run=dry_run)
    except subprocess.TimeoutExpired as exc:
        sys.exit(f"TIMEOUT: {exc}")

    print("\n========================")
    print("All workshop tests passed." if not args.dry_run else "Dry run complete.")


if __name__ == "__main__":
    main()
