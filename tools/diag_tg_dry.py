"""READ-ONLY: Telegram dry run (what would be posted) for the daily and weekly reports; prints captions, PDF sizes, polls."""
import subprocess
import sys

for kind in ("daily", "weekly"):
    print(f"===== {kind}")
    r = subprocess.run([sys.executable, "-m", "tg.post", "--kind", kind, "--dry-run"], capture_output=True, text=True)
    print(r.stdout[-6000:])
    print(r.stderr[-3000:])
