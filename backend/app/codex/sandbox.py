import json
import os
import shutil
from pathlib import Path

PROFILE = "intent-worker"
WORKER_TOOLS = ("git", "node", "python", "uv", "rg")
# MXC cannot grant the drive root, and Node's realpath stats it before loading any script.
# The user's .gitconfig stays unreadable, and git treats an unreadable global config as fatal.
WORKER_ENVIRONMENT = {
    "NODE_OPTIONS": "--preserve-symlinks-main --preserve-symlinks",
    "GIT_CONFIG_GLOBAL": os.devnull,
}


def tool_paths() -> list[Path]:
    paths = []
    for name in WORKER_TOOLS:
        executable = shutil.which(name)
        if not executable:
            continue
        directory = Path(executable).parent
        paths.append(directory)
        config = directory.parent / "pyvenv.cfg"
        if config.is_file():
            paths.append(directory.parent)
            for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
                key, _, value = line.partition("=")
                if key.strip() == "home":
                    paths.append(Path(value.strip()))
    return paths


def readable_paths(project: str, home: str) -> list[str]:
    # Codex runs its own helpers from the profile; its auth.json sits beside them, unlisted.
    roots = [Path(project), Path(home) / ".sandbox-bin", Path(home) / "tmp", *tool_paths()]
    # uv's Python and many tool folders are junctions: the linked and real paths are both needed.
    variants = {variant for root in roots for variant in (Path(os.path.abspath(root)), root.resolve())}
    programs = {os.environ.get(name) for name in ("ProgramFiles", "ProgramFiles(x86)")} - {None}
    return sorted({path.as_posix() for path in variants} | {Path(path).as_posix() for path in programs})


def app_server_arguments(project: str, home: str) -> list[str]:
    """Windows worker sandbox: MXC, no network, and reads only from what a worker needs."""
    if os.name != "nt":
        return []
    rules = [
        '":minimal" = "read"',
        '":workspace_roots" = { "." = "write" }',
        *(f'{json.dumps(path)} = "read"' for path in readable_paths(project, home)),
    ]
    environment = ", ".join(f"{key} = {json.dumps(value)}" for key, value in WORKER_ENVIRONMENT.items())
    return [
        "-c",
        f'default_permissions="{PROFILE}"',
        "-c",
        'windows.sandbox="mxc"',
        "-c",
        f"permissions.{PROFILE}.network.enabled=false",
        "-c",
        f"shell_environment_policy.set={{ {environment} }}",
        "-c",
        f"permissions.{PROFILE}.filesystem={{ {', '.join(rules)} }}",
    ]
