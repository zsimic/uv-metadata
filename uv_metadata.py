from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from abc import ABC, abstractmethod
from importlib.metadata import PathDistribution
from pathlib import Path
from typing import NoReturn
from zipfile import ZipFile

import pyproject_hooks
from build import ProjectBuilder
from build.env import IsolatedEnv
from seekablehttpfile import SeekableHttpFile

METADATA_FILES = ("METADATA", "PKG-INFO", "entry_points.txt", "top_level.txt")
_INFO_DIR_RX = re.compile(r"^(.+\.(dist|egg)-info)/(" + "|".join(re.escape(f) for f in METADATA_FILES) + r")$")
_ROOT_PKG_INFO_RX = re.compile(r"^([^/]+)/PKG-INFO$")
UV_PATH = shutil.which("uv")


def abort(msg: str = "") -> NoReturn:
    sys.exit(msg)


def abort_if(condition, msg: str = ""):
    if condition:
        sys.exit(msg)


def canonical_git_url(url: str) -> str:
    if url.startswith("git@"):
        # Autocorrect default git SSH URLs (allows copy-pasting from github.com)
        url = "git+ssh://" + url.replace(":", "/", 1)

    elif url.startswith("https://") and not url.endswith(".git"):
        url = f"git+{url}"

    return url


def run_uv(*args, fatal=True, env=None, input=None):
    assert UV_PATH is not None
    full_cmd = [UV_PATH, *args]
    result = subprocess.run(full_cmd, input=input, capture_output=True, check=False, env=env, text=True)
    if result.returncode:
        args = " ".join(x for x in args)
        abort_if(fatal, f"'uv {args}' failed with exit code {result.returncode}:\n{result.stderr}")

    return result


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def get_metadata_from_pip_spec(pip_spec: str, python: str | None = None) -> dict:
    """
    Get metadata for a package, routing to the best extraction strategy:

    - local folder (contains pyproject.toml or setup.py) → build metadata via ProjectBuilder
    - local *.dist-info or *.egg-info folder → read directly
    - local .whl or .tar.gz file → extract from archive
    - git URL or direct reference → install to temp dir, read dist-info
    - plain package name (optionally version-constrained) → resolve via uv without installing,
      then stream only the metadata from the remote wheel (much faster than a full install)

    Examples::

        get_metadata_from_pip_spec(".")
        get_metadata_from_pip_spec("requests")
        get_metadata_from_pip_spec("requests>=2.28")
        get_metadata_from_pip_spec("./dist/mypackage-1.0.0.whl")
        get_metadata_from_pip_spec("git+https://github.com/user/repo@main")
    """
    if not pip_spec:
        pip_spec = str(Path(".").absolute())

    # Path-like: starts with common path prefixes or is an existing file/dir
    if pip_spec.startswith(("~", ".", "/")) or os.path.exists(pip_spec):
        path = Path(pip_spec).expanduser().resolve()
        if not path.is_dir():
            abort_if(not path.name.lower().endswith((".whl", ".zip", ".tar.gz")), f"Unknown package type '{path.name}'")
            return extract_metadata_from_file(path)

        if path.name.lower().endswith("-info"):
            return extract_metadata_from_dist_info(path)

        return extract_metadata_from_project_folder(path, python)

    if "://" in pip_spec or pip_spec.startswith("git@") or (" @ " in pip_spec):
        # Git SSH shorthand: git@github.com:user/repo  or direct reference: pkg @ url
        return extract_metadata_from_uv_install(canonical_git_url(pip_spec), python)

    # Plain package name (optionally version-constrained): use fast resolve path
    return extract_metadata_from_uv_resolve(pip_spec, python)


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------


def extract_metadata_from_dist_info(folder: Path) -> dict:
    """Convert a .(egg|dist)-info directory to a clean metadata dict via importlib.metadata"""
    dist = PathDistribution(folder)
    if not dist.metadata:
        abort(f"No metadata files in {folder.name}")

    result: dict = {}
    for key, value in dist.metadata.json.items():
        if isinstance(value, list):
            value = [v for v in value if v != "UNKNOWN"]

        elif value == "UNKNOWN":
            value = None

        if value:
            result[key] = value

    eps = dist.entry_points
    if eps:
        grouped: dict = {}
        for ep in eps:
            grouped.setdefault(ep.group, {})[ep.name] = ep.value

        result["entry_points"] = grouped

    top_level = dist.read_text("top_level.txt")
    if top_level:
        result["top_level"] = top_level.strip().splitlines()

    return result


def extract_metadata_from_project_folder(project_folder: Path, python: str | None = None) -> dict:
    """Build package metadata from a source tree using PEP 517 (via the 'build' library)"""
    abort_if(not project_folder.is_dir(), "folder does not exist")
    abort_if(
        not (project_folder / "pyproject.toml").exists() and not (project_folder / "setup.py").exists(),
        "no pyproject.toml or setup.py",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        venv_folder = tmpdir_path / ".venv"
        env = dict(os.environ)
        env["UV_VENV_SEED"] = "0"
        env["VIRTUAL_ENV"] = str(venv_folder)
        venv_args = ["venv"]
        if python:
            venv_args.append(f"-p{python}")

        run_uv(*venv_args, str(venv_folder), env=env)
        isolated_env = _UvIsolatedEnv(venv_folder)
        builder = ProjectBuilder.from_isolated_env(isolated_env, project_folder, runner=pyproject_hooks.quiet_subprocess_runner)
        isolated_env.install(builder.build_system_requires)
        isolated_env.install(builder.get_requires_for_build("wheel"))
        meta_path = builder.metadata_path(tmpdir_path)
        return extract_metadata_from_dist_info(Path(meta_path))


def extract_metadata_from_file(path: Path) -> dict:
    """Extract metadata from a local .whl or .tar.gz file"""
    abort_if(not path.is_file(), f"File '{path}' does not exist")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        reader_type = ZipReader if path.name.lower().endswith((".whl", ".zip")) else TarReader
        with reader_type(path) as reader:
            return reader.extracted_metadata_members(tmpdir_path)


def extract_metadata_from_uv_install(pip_spec: str, python: str | None = None) -> dict:
    """Install package to a temp dir and read the resulting dist-info (used for git/URL specs)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "target"
        args = ["-q", "pip", "install", "--no-deps", "--target", str(target)]
        if python:
            args.append(f"-p{python}")
        args.append(pip_spec)
        run_uv(*args)
        info = list(target.glob("*.dist-info"))
        abort_if(len(info) != 1, f"expected 1 dist-info folder, got: {[p.name for p in info]}")
        return extract_metadata_from_dist_info(info[0])


def extract_metadata_from_uv_resolve(pip_spec: str, python: str | None = None) -> dict:
    """
    Resolve package metadata without installing — much faster than a full install.

    Uses 'uv pip compile --format pylock.toml' to find the wheel URL, then streams
    only the metadata section from the remote .whl via HTTP range requests.
    Falls back to downloading the sdist when no wheel is available.
    """
    args = [
        "-q",
        "pip",
        "compile",
        "--no-deps",
        "--no-header",
        "--universal",
        "--no-sources",
        "--format",
        "pylock.toml",
        "--fork-strategy",
        "fewest",
        "--resolution",
        "highest",
        # Use python-version '99' to get latest metadata regardless of local python.
        # When the caller specifies a python version, honor it so metadata reflects that target.
        "--python-version",
        python or "99",
    ]
    r = run_uv(*args, "-", input=pip_spec, fatal=False)
    if not r.returncode and r.stdout:
        m = re.search(r'\burl\s*=\s*"([^"]+\.whl)"', r.stdout)
        if m:
            wheel_url = m.group(1)
            with tempfile.TemporaryDirectory() as tmpdir:
                streamed = SeekableHttpFile(wheel_url, check_etag=False)
                with ZipReader(streamed) as reader:
                    return reader.extracted_metadata_members(Path(tmpdir))

        # Fallback: download sdist and extract metadata from it
        m = re.search(r'\burl\s*=\s*"([^"]+)"', r.stdout)
        if m:
            return _download_and_extract(m.group(1))

    msg = (r.stderr or "uv resolve failed with an empty stderr").strip()
    if "not found in the package registry" in " ".join(x.strip() for x in msg.splitlines()):
        msg = f"Package '{pip_spec}' does not exist"

    abort(msg)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _download_and_extract(url: str) -> dict:
    """Download an archive from a URL and extract metadata from it"""
    from urllib.request import urlopen

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / url.rsplit("/", 1)[-1]
        with urlopen(url) as resp:
            dest.write_bytes(resp.read())

        return extract_metadata_from_file(dest)


class MetadataReader(ABC):
    """Context manager that abstracts extraction of metadata from zip/tar files"""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    @abstractmethod
    def close(self) -> None:
        """Release underlying archive resources"""

    def find_metadata_members(self) -> list:
        """Find archive members containing package metadata.

        Prefers .dist-info/.egg-info directories, falls back to root-level PKG-INFO.
        """
        members = self.getmembers()
        matched = [m for m in members if _INFO_DIR_RX.match(self.filepath(m))]
        if not matched:
            matched = [m for m in members if _ROOT_PKG_INFO_RX.match(self.filepath(m))]

        abort_if(not matched, f"No metadata found in {self}")
        return matched

    def extracted_metadata_members(self, tmpdir: Path) -> dict:
        members = self.find_metadata_members()
        info_dir = tmpdir / "tmp.dist-info"
        info_dir.mkdir()
        for m in members:
            b = self.read_bytes(m)
            name = os.path.basename(self.filepath(m))
            if name == "PKG-INFO":
                name = "METADATA"

            (info_dir / name).write_bytes(b)

        return extract_metadata_from_dist_info(info_dir)

    @abstractmethod
    def filepath(self, member) -> str:
        """Path of `member` within the archive"""

    @abstractmethod
    def getmembers(self) -> list:
        """Return a list of contained file members"""

    @abstractmethod
    def read_bytes(self, member) -> bytes:
        """Read bytes from `member`"""


class ZipReader(MetadataReader):
    def __init__(self, source: Path | SeekableHttpFile):
        self.source = source
        self.zip_file = ZipFile(source)  # type: ignore[arg-type]

    def __repr__(self):
        return str(self.source)

    def close(self) -> None:
        self.zip_file.close()

    def filepath(self, member) -> str:
        return member.filename

    def getmembers(self) -> list:
        return self.zip_file.filelist

    def read_bytes(self, member) -> bytes:
        return self.zip_file.read(member.filename)


class TarReader(MetadataReader):
    def __init__(self, path: Path):
        self.path = path
        self.tar_file = tarfile.open(path)

    def __repr__(self):
        return str(self.path)

    def close(self) -> None:
        self.tar_file.close()

    def filepath(self, member) -> str:
        return member.name

    def getmembers(self) -> list:
        return self.tar_file.getmembers()

    def read_bytes(self, member) -> bytes:
        f = self.tar_file.extractfile(member)
        return f.read() if f else b""


class _UvIsolatedEnv(IsolatedEnv):
    def __init__(self, venv_folder: Path):
        self.venv_folder = venv_folder

    @property
    def python_executable(self) -> str:
        return str(self.venv_folder / "bin/python")

    def make_extra_environ(self) -> dict:
        return {}

    def install(self, requirements) -> None:
        if requirements:
            run_uv("pip", "install", "--python", self.python_executable, *requirements)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(args=None):
    """
    Output the metadata of a package, in machine-readable format

    Examples:
        uv-metadata requests
        uv-metadata "requests>=2.28"
        uv-metadata .
        uv-metadata ./dist/mypackage-1.0.0.whl
        uv-metadata ./dist/mypackage-1.0.0.tar.gz
        uv-metadata git+https://github.com/zsimic/uv-metadata@main
    """
    parser = argparse.ArgumentParser(description=main.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-p", "--python", help="Python version to target (e.g. 3.11)")
    parser.add_argument("-k", "--key", help="Show only this key from the metadata")
    parser.add_argument("--full", action="store_true", help="Include full description in output")
    parser.add_argument("package", default=None, nargs="?", help="Package to inspect (default: current folder)")
    args = parser.parse_args(args=args)

    meta_dict = get_metadata_from_pip_spec(args.package, args.python)
    if not args.full:
        meta_dict.pop("description", None)
        meta_dict.pop("dynamic", None)

    if args.key is None:
        print(json.dumps(meta_dict, indent=4, sort_keys=True))

    else:
        value = meta_dict.get(args.key)
        abort_if(value is None, f"no key '{args.key}' in metadata")
        print(value if isinstance(value, str) else json.dumps(value, indent=4, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
