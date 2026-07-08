from __future__ import annotations

import re
from pathlib import Path


INCLUDE_PATTERN = re.compile(r"{{\s*include:\s*([^{}\s]+)\s*}}")


class PromptIncludeError(ValueError):
    """Raised when a prompt contract include cannot be resolved safely."""


def resolve_prompt_includes(
    prompt_path: Path,
    *,
    root: Path,
    max_depth: int = 8,
    _seen: tuple[Path, ...] = (),
) -> str:
    root = root.resolve()
    resolved_prompt_path = prompt_path.resolve()

    try:
        resolved_prompt_path.relative_to(root)
    except ValueError as exc:
        raise PromptIncludeError(f"Include path escapes repository root: {prompt_path}") from exc

    if resolved_prompt_path in _seen:
        chain = " -> ".join(path.relative_to(root).as_posix() for path in (*_seen, resolved_prompt_path))
        raise PromptIncludeError(f"Recursive prompt include detected: {chain}")

    if len(_seen) >= max_depth:
        raise PromptIncludeError(f"Prompt include depth exceeds {max_depth}: {prompt_path}")

    if not resolved_prompt_path.exists():
        raise PromptIncludeError(f"Missing prompt include target: {prompt_path}")

    text = resolved_prompt_path.read_text(encoding="utf-8")
    seen = (*_seen, resolved_prompt_path)

    def replace_include(match: re.Match[str]) -> str:
        include_value = match.group(1)
        include_path = (root / include_value).resolve()
        try:
            include_path.relative_to(root)
        except ValueError as exc:
            raise PromptIncludeError(f"Include path escapes repository root: {include_value}") from exc
        return resolve_prompt_includes(include_path, root=root, max_depth=max_depth, _seen=seen)

    return INCLUDE_PATTERN.sub(replace_include, text)
