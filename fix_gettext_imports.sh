#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# fix_gettext_imports.sh
#
# Find Python files that call _('...') but forgot to import
#     from django.utils.translation import gettext_lazy as _
# and add the missing import automatically.
#
# Usage:
#   chmod +x fix_gettext_imports.sh
#   ./fix_gettext_imports.sh
# ---------------------------------------------------------------------------

set -euo pipefail

# Root of the repo (works whether you’re inside or outside Git)
ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
APP_ROOT="$ROOT_DIR/apps"

printf "🔍  Scanning %s for missing gettext_lazy imports…\n" "$APP_ROOT"

files_fixed=0

# 1) find .py files that contain "_(" **and** are missing "gettext_lazy as _"
while IFS= read -r -d '' file; do
    if ! grep -q "gettext_lazy as _" "$file"; then
        printf "→  Fixing %s\n" "${file#$ROOT_DIR/}"

        # make a timestamped backup
        cp "$file" "${file}.bak.$(date +%Y%m%d%H%M%S)"

        # insert the import right after the first import line
        awk '
            BEGIN {inserted=0}
            /^[[:space:]]*(from|import)[[:space:]]+/ && inserted==0 {
                print
                print "from django.utils.translation import gettext_lazy as _"
                inserted=1
                next
            }
            {print}
        ' "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"

        files_fixed=$((files_fixed+1))
    fi
done < <(
    # -R recursive   -l list files only   -Z NUL-delimited   --include restrict extension
    grep -Rlz --include="*.py" "_(" "$APP_ROOT" | grep -v "/migrations/"
)

printf "✅  Done. Added import in %d file(s).\n" "$files_fixed"
