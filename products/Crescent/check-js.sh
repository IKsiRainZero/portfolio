#!/usr/bin/env bash
# JS syntax check — run before committing frontend changes
# Usage: bash check-js.sh
set -e
cd "$(dirname "$0")/static/js"
echo "=== JS Syntax Check ==="
fail=0
for f in app.js modules/*.js; do
  if node -e "try { new Function(require('fs').readFileSync('$f','utf8')); } catch(e) { process.exit(1); }"; then
    echo "  OK  $f"
  else
    echo "  FAIL $f"
    node -e "try { new Function(require('fs').readFileSync('$f','utf8')); } catch(e) { console.log('     ', e.message); }"
    fail=1
  fi
done
if [ $fail -eq 0 ]; then echo "=== All OK ==="; else echo "=== FAILED ==="; fi
exit $fail
