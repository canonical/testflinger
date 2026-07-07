"""
Smoke-test the workshop dev actions defined in .workshop/dev.yaml.

Each action is run via `workshop run dev <action>`.  The sequence mirrors
the documented workflow:

    serve  →  populate-quick  →  logs (timed)  →  teardown

restart = teardown + serve, so it is tested as its own round-trip too.

Usage:
    python test_workshop_actions.py          # full sequence
    python test_workshop_actions.py --dry-run  # print commands only
"""

import argparse
import shutil
import subprocess
import sys
import time

WORKSHOP = "workshop"
WORKSHOP_ACTION = ["workshop", "run", "dev"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def check_prerequisites() -> None:
    """Abort immediately if the workshop CLI is not on PATH."""
    if shutil.which(WORKSHOP) is None:
        sys.exit(
            f"ERROR: '{WORKSHOP}' CLI not found on PATH. "
            "This script must run inside a workshop container."
        )


def run(action: str, *extra_args: str, timeout: int = 120, dry_run: bool = False) -> None:
    """Run `workshop run dev <action> [extra_args]`, fail fast on error."""
    cmd = WORKSHOP_ACTION + [action] + list(extra_args)
    print(f"\n>>> {' '.join(cmd)}")
    if dry_run:
        return
    result = subprocess.run(cmd, timeout=timeout)
    if result.returncode != 0:
        sys.exit(f"FAILED: action '{action}' exited with code {result.returncode}")


def run_logs(duration: int = 10, dry_run: bool = False) -> None:
    """
    Run the `logs` action for *duration* seconds then send SIGINT (like Ctrl-C).

    The action tails docker compose logs with --follow, so it never exits on
    its own; we interrupt it after a short window just to confirm it streams
    without immediately crashing.
    """
    cmd = WORKSHOP_ACTION + ["logs"]
    print(f"\n>>> {' '.join(cmd)}  (will interrupt after {duration}s)")
    if dry_run:
        return
    proc = subprocess.Popen(cmd)
    time.sleep(duration)
    proc.send_signal(__import__("signal").SIGINT)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    # logs is a streaming command; any exit code is acceptable here
    print(f"    logs streamed for {duration}s — OK")


# ---------------------------------------------------------------------------
# Test steps
# ---------------------------------------------------------------------------


def test_serve(dry_run: bool) -> None:
    print("\n=== 1. serve ===")
    run("serve", dry_run=dry_run)


def test_logs(dry_run: bool) -> None:
    print("\n=== 2. logs (10s smoke test) ===")
    run_logs(duration=10, dry_run=dry_run)


def test_populate_quick(dry_run: bool) -> None:
    print("\n=== 3. populate-quick ===")
    # populate-quick hits localhost:5000; give docker a moment to be ready
    if not dry_run:
        print("    waiting 5s for server to be ready…")
        time.sleep(5)
    run("populate-quick", timeout=300, dry_run=dry_run)


def test_restart(dry_run: bool) -> None:
    print("\n=== 4. restart (teardown + serve) ===")
    run("restart", dry_run=dry_run)


def test_teardown(dry_run: bool) -> None:
    print("\n=== 5. teardown ===")
    run("teardown", dry_run=dry_run)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them")
    args = parser.parse_args()

    if not args.dry_run:
        check_prerequisites()

    print("Workshop dev action smoke tests")
    print("================================")

    try:
        test_serve(args.dry_run)
        test_logs(args.dry_run)
        test_populate_quick(args.dry_run)
        test_restart(args.dry_run)
        test_logs(args.dry_run)   # confirm logs still work after restart
        test_teardown(args.dry_run)
    except subprocess.TimeoutExpired as exc:
        sys.exit(f"TIMEOUT: {exc}")

    print("\n================================")
    print("All workshop actions passed." if not args.dry_run else "Dry run complete.")


if __name__ == "__main__":
    main()
