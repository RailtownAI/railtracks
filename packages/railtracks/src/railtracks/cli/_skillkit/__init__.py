"""Everything behind `railtracks add`: reading skills, installing them, tracking them.

Three layers, in dependency order:

* `registry` — the on-disk skill format and the discovery that reads it. Knows nothing
  about installing.
* `manifest` — the record an install leaves behind, so the next one can be a sync.
* `install` — the directory copy itself, parameterised per assistant.

Private to the CLI (hence the underscore): the names re-exported here are what
`railtracks.cli` needs, and the layout inside is free to change without notice.

The bundled skill *content* deliberately does not live here. It stays at
`cli/skills/<name>/SKILL.md`, because `discover_skills()` treats every directory under
that root as a skill and would reject a Python package sitting among them.
"""

from .install import CLAUDE, InstallTarget, install_skill_directory
from .manifest import (
    MANIFEST_FILE,
    InstallRecord,
    find_legacy_installs,
    package_version,
    read_record,
)
from .registry import (
    Skill,
    SkillFormatError,
    default_skills_directory,
    discover_skills,
    load_skill,
)

__all__ = [
    "CLAUDE",
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
]
