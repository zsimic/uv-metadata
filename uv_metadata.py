import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from importlib.metadata import PathDistribution
from pathlib import Path
from typing import NoReturn
from zipfile import ZipFile

import pyproject_hooks
from build import ProjectBuilder
from build.env import IsolatedEnv
from seekablehttpfile import SeekableHttpFile

METADATA_FILES = ("METADATA", "PKG-INFO", "entry_points.txt", "top_level.txt")
UV_PATH = shutil.which("uv")


def abort(msg: str = "") -> NoReturn:
    sys.exit(msg)


def abort_if(condition, msg: str = ""):
    if condition:
        sys.exit(msg)


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


def get_metadata_from_pip_spec(pip_spec: str | None, python: str | None = None) -> dict:
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

    # Git SSH shorthand: git@github.com:user/repo  or direct reference: pkg @ url
    if "://" in pip_spec or pip_spec.startswith("git@") or (" @ " in pip_spec):
        if pip_spec.startswith("git@"):
            # Autocorrect default git SSH URLs (allows copy-pasting from github.com)
            pip_spec = "git+ssh://" + pip_spec.replace(":", "/", 1)

        return extract_metadata_from_uv_install(pip_spec, python)

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

    result: dict = dict(dist.metadata.json)
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
        if path.name.lower().endswith((".whl", ".zip")):
            with ZipFile(path) as zf:
                return _extract_from_zipfile(zf, tmpdir_path)

        return _extract_from_tarball(path, tmpdir_path)


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
    Aborts if the package has no wheel (sdist-only packages are not supported here).
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
    if r.returncode:
        msg = r.stderr.strip()
        if "not found in the package registry" in " ".join(x.strip() for x in msg.splitlines()):
            msg = f"Package '{pip_spec}' does not exist"

        abort(msg)

    m = re.search(r'\burl\s*=\s*"([^"]+\.whl)"', r.stdout)
    if not m:
        abort(f"No wheel available for {pip_spec}")

    wheel_url = m.group(1)
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            streamed = ZipFile(SeekableHttpFile(wheel_url, check_etag=False))  # type: ignore[arg-type]

        except Exception as e:  # pragma: no cover
            abort(f"Can't stream wheel for {pip_spec}: {e}")

        return _extract_from_zipfile(streamed, Path(tmpdir))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_dist_info_files(info_dir: Path, prefix: str, names: set[str], read_fn) -> None:
    """Copy dist-info metadata files from an archive into info_dir"""
    info_dir.mkdir(parents=True, exist_ok=True)
    for filename in METADATA_FILES:
        src = f"{prefix}/{filename}"
        if src in names:
            dest = "METADATA" if filename == "PKG-INFO" else filename
            (info_dir / dest).write_bytes(read_fn(src))


def _extract_from_zipfile(zf: ZipFile, tmpdir: Path) -> dict:
    """Extract metadata from an open ZipFile (local wheel or streamed remote wheel)"""
    names = set(zf.namelist())
    for name in zf.namelist():
        m = re.match(r"^([^/]+\.dist-info)/(?:METADATA|PKG-INFO)$", name)
        if m:
            info_dir = tmpdir / m.group(1)
            _extract_dist_info_files(info_dir, m.group(1), names, zf.read)
            return extract_metadata_from_dist_info(info_dir)

    abort("No dist-info found in wheel")


def _extract_from_tarball(path: Path, tmpdir: Path) -> dict:
    """Extract metadata from an sdist .tar.gz"""
    with tarfile.open(path) as tf:
        members = {m.name: m for m in tf.getmembers() if m.isfile()}
        names = set(members.keys())

        def read_fn(src: str) -> bytes:
            f = tf.extractfile(members[src])
            return f.read() if f else b""

        for name in members:
            m = re.search(r"^(.+\.(dist|egg)-info)/(?:METADATA|PKG-INFO)$", name)
            if m:
                prefix = m.group(1)
                info_dir = tmpdir / Path(prefix).name
                _extract_dist_info_files(info_dir, prefix, names, read_fn)
                return extract_metadata_from_dist_info(info_dir)

        # Fallback: root-level PKG-INFO (some older sdists)
        for name in members:
            m = re.match(r"^([^/]+)/PKG-INFO$", name)
            if m:
                fake_info = tmpdir / "package.dist-info"
                _extract_dist_info_files(fake_info, m.group(1), names, read_fn)
                return extract_metadata_from_dist_info(fake_info)

    abort(f"No metadata found in {path.name}")


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
    parser.add_argument("package", default=None, nargs="?", help="Package to inspect (default: current folder)")
    args = parser.parse_args(args=args)

    meta_dict = get_metadata_from_pip_spec(args.package, args.python)
    if args.key is None:
        print(json.dumps(meta_dict, indent=4, sort_keys=True))

    else:
        value = meta_dict.get(args.key)
        abort_if(value is None, f"no key '{args.key}' in metadata")
        print(value if isinstance(value, str) else json.dumps(value, indent=4, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
