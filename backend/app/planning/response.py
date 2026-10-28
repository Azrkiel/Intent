"""Render common drawing glyphs in new provider responses, never stored plans."""

import json

_DRAWING_GLYPHS = str.maketrans({
    **dict.fromkeys("\u2500\u2501\u2550", "-"),
    **dict.fromkeys("\u2502\u2503\u2551", "|"),
    **dict.fromkeys("\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534\u253c"
                    "\u2554\u2557\u255a\u255d\u2560\u2563\u2566\u2569\u256c\u256d\u256e\u256f\u2570", "+"),
    "\u2192": "->", "\u2190": "<-", "\u2194": "<->",
    "\u21d2": "=>", "\u21d0": "<=", "\u21d4": "<=>",
    "\u2191": "^", "\u2193": "v",
})


def diagram_response(role: str, content: str) -> str:
    """Only declared diagram fields change; all subsequent validators still apply."""
    if not (role == "planner:outline" or role.startswith(("planner:screen:", "planner:phase:"))):
        return content
    try:
        value = json.loads(content)
    except (ValueError, RecursionError):
        return content
    if not isinstance(value, dict):
        return content

    def convert(container, field):
        if isinstance(container, dict) and isinstance(container.get(field), str):
            container[field] = container[field].translate(_DRAWING_GLYPHS)

    if role == "planner:outline":
        convert(value, "architecture")
    elif role.startswith("planner:screen:"):
        wireframes = value.get("wireframes")
        for state in ("empty", "loading", "error", "success"):
            convert(wireframes, state)
    else:
        convert(value, "flow")
        packages = value.get("packages")
        if isinstance(packages, list):
            for package in packages:
                convert(package, "flow")
    return json.dumps(value, ensure_ascii=True)
