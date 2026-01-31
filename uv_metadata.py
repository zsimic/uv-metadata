import argparse
import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from email.parser import Parser
from pathlib import Path
from typing import Collection

import pyproject_hooks
from build import ProjectBuilder
from build.env import IsolatedEnv

# See https://github.com/jwilk-mirrors/python-pkginfo/blob/master/pkginfo/distribution.py#L34
CANONICAL_KEY = {
    "classifier": "classifiers"  # PEP 301
}
# The others seem super-minor, and are not respected even by pypi.org, so ignoring for now
# Example https://pypi.org/pypi/uv/json


def abort_if(condition, msg: str):
    if condition:
        sys.exit(msg)


def run_command(exe, *args, fatal=True):
    exe = shutil.which(exe)
    full_cmd = [exe, *args]
    result = subprocess.run(full_cmd, capture_output=True, text=True, check=False)
    if result.returncode:
        description = "%s %s" % (exe, " ".join(str(x) for x in args))
        abort_if(fatal, f"'{description}' failed with exit code {result.returncode}:\n{result.stderr}")

    return result


def canonical_key(key: str) -> str:
    key = re.sub(r"[^\w]", "_", key).lower()
    if key in CANONICAL_KEY:
        return CANONICAL_KEY[key]

    return key


class UvIsolatedEnv(IsolatedEnv):
    def __init__(self, venv_folder: Path):
        self.venv_folder = venv_folder

    @property
    def python_executable(self) -> str:
        return str(self.venv_folder / "bin/python")

    def make_extra_environ(self) -> dict:
        return {}

    def install(self, requirements: Collection[str]) -> None:
        if requirements:
            run_command("uv", "pip", "install", "--python", self.python_executable, *requirements)


def get_metadata_dict(path):
    result = {}
    if path.exists():
        parser = Parser()
        with open(path, "r") as fh:
            raw = parser.parse(fh, headersonly=False)
            for key, value in raw.items():
                if key == "Dynamic":
                    continue

                if key not in result:
                    result[key] = value
                    continue

                prev = result.get(key)
                if isinstance(prev, list):
                    prev.append(value)

                else:
                    result[key] = [prev, value]

        result = {canonical_key(k): v for k, v in result.items()}

    return result


def parse_dist_info(full_path: Path) -> dict:
    metadata = get_metadata_dict(full_path / "METADATA")
    entry_points = full_path / "entry_points.txt"
    if entry_points.exists():
        config = configparser.ConfigParser()
        config.read(entry_points)
        eps = {section: dict(config.items(section)) for section in config.sections()}
        if eps:
            metadata["entry_points"] = eps

    top_level = full_path / "top_level.txt"
    if top_level.exists():
        with open(top_level, "r") as fh:
            metadata["top_level"] = fh.read().splitlines()

    return metadata


def get_metadata(pip_spec: str, python: str) -> dict:
    os.environ["UV_VENV_SEED"] = "0"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        venv_folder = tmpdir / ".venv"
        os.environ["VIRTUAL_ENV"] = str(venv_folder)
        run_command("uv", "venv", f"-p{python}", venv_folder)
        if isinstance(pip_spec, Path):
            meta_dir = venv_folder / "dist-info"
            meta_dir.mkdir(parents=True, exist_ok=True)
            env = UvIsolatedEnv(venv_folder)
            builder = ProjectBuilder.from_isolated_env(env, pip_spec, runner=pyproject_hooks.quiet_subprocess_runner)
            env.install(builder.build_system_requires)
            env.install(builder.get_requires_for_build("wheel"))
            meta_path = builder.metadata_path(output_directory=meta_dir)
            abort_if(not meta_path, "Failed to build metadata")
            return parse_dist_info(Path(meta_path))

        run_command("uv", "pip", "install", "--no-deps", pip_spec)
        r = run_command("uv", "pip", "freeze")
        frozen = r.stdout.splitlines()
        abort_if(len(frozen) != 1, f"Unexpected pip freeze output:\n{r.stdout}")
        package_name = frozen[0]
        if "@" in package_name:
            package_name = package_name.partition("@")[0].strip()

        else:
            package_name = package_name.partition("=")[0].strip()

        r = run_command("uv", "pip", "show", package_name)
        raw_metadata = Parser().parsestr(r.stdout)
        version = raw_metadata["Version"]
        wheel_name = re.sub(r"[^\w]", "_", raw_metadata["Name"]).lower()
        full_path = Path(raw_metadata["Location"]) / f"{wheel_name}-{version}.dist-info"
        return parse_dist_info(full_path)


def main(args=None):
    """
    Output the metadata of a package, in machine-readable format

    Examples:
        uv-metadata requests
        uv-metadata .
        uv-metadata git+https://github.com/zsimic/uv-metadata@main
    """
    parser = argparse.ArgumentParser(description=main.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    syspy = f"{sys.version_info[0]}.{sys.version_info[1]}"
    parser.add_argument("-p", "--python", default=syspy, help="Python interpreter to use (default: %(default)s)")
    parser.add_argument("-k", "--key", help="Show only this key from the metadata")
    parser.add_argument("package", default=".", nargs="?", help="Show metadata for specified package")
    args = parser.parse_args(args=args)

    key = args.key
    package = args.package
    python = args.python
    if package.startswith((".", "/", "~")):
        package = (Path(package).expanduser()).absolute()

    metadata = get_metadata(package, python)
    if key:
        abort_if(key not in metadata, f"'{key}' not found in metadata")
        text = metadata[key]

    else:
        text = json.dumps(metadata, indent=4, sort_keys=True)

    print(text)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
