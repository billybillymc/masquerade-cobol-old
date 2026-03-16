"""File discovery: walk COBOL source trees, filter by extension, classify files."""

import os
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag_config import COBOL_EXTENSIONS, COPYBOOK_EXTENSIONS, JCL_EXTENSIONS, CODEBASES


def _classify_cobol_file(file_path: str) -> str:
    """Classify a COBOL file by naming convention."""
    name = os.path.basename(file_path).upper()
    ext = os.path.splitext(name)[1]

    if ext in ('.CPY',):
        return "copybook"
    if ext in ('.JCL',):
        return "jcl"

    if name.startswith("CB"):
        return "batch"
    if name.startswith("CO"):
        return "online"
    return "source"


def scan_source_files(
    base_path: str = None,
    codebase: str = "default",
) -> List[Dict[str, str]]:
    """Discover all indexable COBOL files under a source path.

    Returns list of dicts: path, rel_path, extension, category, codebase.
    """
    cb_config = CODEBASES.get(codebase, {})
    if base_path is None:
        base_path = cb_config.get("src_path", ".")
    valid_extensions = cb_config.get("extensions", COBOL_EXTENSIONS | COPYBOOK_EXTENSIONS | JCL_EXTENSIONS)
    skip_dirs = cb_config.get("skip_dirs", {".git", "_analysis", "__pycache__"})

    results: List[Dict[str, str]] = []
    base = Path(base_path)

    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for filename in files:
            ext = os.path.splitext(filename)[1]
            if ext.lower() not in {e.lower() for e in valid_extensions}:
                continue

            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, base).replace("\\", "/")
            category = _classify_cobol_file(filename)

            results.append({
                "path": full_path,
                "rel_path": rel_path,
                "extension": ext.lower(),
                "category": category,
                "codebase": codebase,
            })

    return results
