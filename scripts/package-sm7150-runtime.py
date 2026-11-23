#!/usr/bin/env python3
"""
package-sm7150-runtime.py:
Packages the OneiOS runtime for Snapdragon 730G (SM7150 - Galaxy M51 & A71)
incorporating iOS 16 iPhone X and host hardware profiles.
"""

import hashlib
import json
import os
import stat
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def update_runtime_manifest(runtime_dir: Path) -> Path:
    runtime_json_path = runtime_dir / "runtime.json"
    if not runtime_json_path.is_file():
        raise FileNotFoundError(f"Missing runtime.json in {runtime_dir}")

    with open(runtime_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Collect all files recursively except runtime.json
    files_list = []
    for root, _, filenames in os.walk(runtime_dir):
        for fname in sorted(filenames):
            if fname == "runtime.json":
                continue
            full_path = Path(root) / fname
            rel_path = full_path.relative_to(runtime_dir).as_posix()
            file_size = full_path.stat().st_size
            file_sha = sha256_file(full_path)

            # Determine mode
            st_mode = full_path.stat().st_mode
            if rel_path.startswith("bin/") or bool(st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
                mode_str = "0755"
            else:
                mode_str = "0644"

            files_list.append({
                "path": rel_path,
                "size": file_size,
                "sha256": file_sha,
                "mode": mode_str
            })

    # Sort files by path for deterministic verification
    files_list.sort(key=lambda x: x["path"])
    data["files"] = files_list

    with open(runtime_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"Updated {runtime_json_path} with {len(files_list)} verified files.")
    return runtime_json_path


if __name__ == "__main__":
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("runtime_pkg")
    update_runtime_manifest(target_dir)
