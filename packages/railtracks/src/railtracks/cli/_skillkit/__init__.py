"""Everything behind `railtracks add`: reading skills, installing them, tracking them.

* `registry` — the on-disk skill format, and the discovery that reads it.
* `manifest` — the record an install leaves in a skill directory.
* `install` — the workflow that copies a skill directory, prunes stale files, and
  writes a manifest. Provider-agnostic; the specifics come from `providers`.
* `providers/` — one `InstallTarget` per supported assistant.

Private to the CLI; the names re-exported below are the surface it uses.
"""

from .install import (
    InstallTarget,
    install_skill_directory,
    strip_skill_arguments,
)
from .manifest import (
    MANIFEST_FILE,
    InstallRecord,
    find_legacy_installs,
    package_version,
    read_record,
)
from .providers import CLAUDE, CODEX, COPILOT, CURSOR
from .registry import (
    Skill,
    SkillFormatError,
    default_skills_directory,
    discover_skills,
    load_skill,
)

__all__ = [
    "CLAUDE",
    "CODEX",
    "COPILOT",
    "CURSOR",
    "InstallRecord",
    "InstallTarget",
    "MANIFEST_FILE",
    "Skill",
    "SkillFormatError",
    "default_skills_directory",
    "discover_skills",
    "find_legacy_installs",
    "install_skill_directory",
    "load_skill",
    "package_version",
    "read_record",
    "strip_skill_arguments",
]
