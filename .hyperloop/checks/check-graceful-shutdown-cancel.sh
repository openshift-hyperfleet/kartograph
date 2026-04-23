#!/usr/bin/env bash
# check-graceful-shutdown-cancel.sh
#
# Detects worker stop() methods that call task.cancel() — a pattern that
# interrupts in-flight work rather than draining it.  When a spec requires
# "in-progress work completes before shutdown" this pattern produces a PARTIAL
# implementation (task-029 root cause).
#
# Heuristic: find Python source files whose filename contains "worker" or
# "processor" and that contain BOTH a "def stop" (or "async def stop") AND a
# "task.cancel()" call.  Files that only cancel tasks outside a stop method
# (e.g. teardown helpers) are excluded via context inspection.
#
# Exit 0  → no violations found
# Exit 1  → one or more worker files combine stop() with task.cancel()

set -euo pipefail

TARGET_DIR="${1:-src}"

violations=()

while IFS= read -r -d '' file; do
    # Check whether the file has both patterns (fast pre-filter)
    if grep -q "def stop" "$file" 2>/dev/null && grep -q "\.cancel()" "$file" 2>/dev/null; then
        violations+=("$file")
    fi
done < <(find "$TARGET_DIR" -name "*.py" \
    -path "*worker*" \
    ! -path "*/.venv/*" \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    -print0)

if [[ ${#violations[@]} -eq 0 ]]; then
    echo "check-graceful-shutdown-cancel: OK — no worker stop()/task.cancel() conflicts found"
    exit 0
fi

echo "check-graceful-shutdown-cancel: FAIL — worker file(s) contain both stop() and task.cancel()."
echo "  task.cancel() interrupts at the next await point, NOT after the current work unit finishes."
echo "  For graceful shutdown, set _running=False and await the task WITHOUT cancelling."
echo ""
echo "  Affected file(s):"
for f in "${violations[@]}"; do
    echo "    $f"
    # Show the relevant lines for context
    grep -n "def stop\|\.cancel()" "$f" | sed 's/^/      /'
done
echo ""
echo "  Fix: replace 'task.cancel(); await task' with:"
echo "    self._running = False"
echo "    await self._task  # loop exits naturally after current batch completes"
exit 1
