"""Single place to bump the PEC version this factory targets.

The pack itself (``scripts/demo/pack/pack.json``) is the source of truth for
which version a given base.backup was built against, and
build-demo-backup.sh reads it from there at runtime. This constant only
covers the fallback defaults used by the CLI and the GraphQL client when
invoked outside that script (manual/dev runs).
"""

from __future__ import annotations

DEFAULT_PEC_VERSION = "5.5.28"
