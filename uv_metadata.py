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

CURRENT_PY = f"{sys.version_info[0]}.{sys.version_info[1]}"


def abort(msg: str):
    sys.exit(msg)


def run_command(exe, *args, fatal=True):
    exe = shutil.which(exe)
    full_cmd = [exe, *args]
    result = subprocess.run(full_cmd, capture_output=True, text=True, check=False)
    if fatal and result.returncode:
        description = "%s %s" % (exe, " ".join(str(x) for x in args))
        abort(f"'{description}' failed with exit code {result.returncode}:\n{result.stderr}")

    return result


def snakified(name: str) -> str:
    return re.sub(r"[^\w]", "_", name).lower()


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

    result = {snakified(k): v for k, v in result.items()}
    return result


def get_metadata(pip_spec: str, python: str) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        run_command("uv", "venv", f"-p{python}")
        run_command("uv", "pip", "install", "--no-deps", pip_spec)
        r = run_command("uv", "pip", "freeze")
        package_name = r.stdout.splitlines()[0]
        if "@" in package_name:
            package_name = package_name.partition("@")[0].strip()

        else:
            package_name = package_name.partition("=")[0].strip()

        r = run_command("uv", "pip", "show", package_name)
        show_metadata = Parser().parsestr(r.stdout)
        name = show_metadata["Name"]
        version = show_metadata["Version"]
        wheel_name = snakified(name)
        full_path = Path(show_metadata["Location"]) / f"{wheel_name}-{version}.dist-info"
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


def main(args=None):
    """
    Output the metadata of a package, in machine-readable format

    \b
    Examples:
        uv-metadata requests
        uv-metadata .
        uv-metadata git+https://github.com/zsimic/uv-metadata@main
    """
    # Ensure we don't let our own venv interfere with uv usage
    os.environ.pop("VIRTUAL_ENV", None)
    os.environ["UV_VENV_SEED"] = "0"
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", "-p", default=CURRENT_PY, help=f"Python interpreter to use (default: {CURRENT_PY})")
    parser.add_argument("--key", "-k", help="Show only this key from the metadata")
    parser.add_argument("package", default=".", nargs="?", help="Show metadata for this package")
    args = parser.parse_args(args=args)

    key = args.key
    package = args.package
    python = args.python
    if package.startswith((".", "/", "~")):
        package = (Path(package).expanduser()).absolute()

    metadata = get_metadata(package, python)
    if key:
        if key not in metadata:
            abort(f"'{key}' not found in metadata")

        text = metadata[key]

    else:
        text = json.dumps(metadata, indent=4, sort_keys=True)

    print(text)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
