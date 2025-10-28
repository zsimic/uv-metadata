import os
import sys
from email.parser import Parser

import click
import runez
from runez.pyenv import PypiStd

CURRENT_PY = f"{sys.version_info[0]}.{sys.version_info[1]}"


def get_metadata(pip_spec: str, python: str) -> dict:
    with runez.TempFolder():
        runez.run("uv", "venv", f"-p{python}")
        runez.run("uv", "pip", "install", "--no-deps", pip_spec)
        r = runez.run("uv", "pip", "freeze")
        lines = r.output.splitlines()
        runez.abort_if(not lines or len(lines) != 1, f"'pip freeze' for '{pip_spec}' failed: {r.full_output}")
        if "@" in lines[0]:
            package_name = lines[0].partition("@")[0].strip()

        else:
            package_name = lines[0].partition("=")[0].strip()

        r = runez.run("uv", "pip", "show", package_name)
        show_metadata = Parser().parsestr(r.output)
        name = show_metadata["Name"]
        location = runez.to_path(show_metadata["Location"])
        version = show_metadata["Version"]
        wheel_name = PypiStd.std_wheel_basename(name)
        dist_info_name = f"{wheel_name}-{version}.dist-info"
        full_path = location / dist_info_name
        metadata = get_metadata_dict(full_path / "METADATA")
        entry_points = runez.file.ini_to_dict(full_path / "entry_points.txt")
        if entry_points:
            metadata["entry_points"] = entry_points

        top_levels = list(runez.file.readlines(full_path / "top_levels.txt"))
        if top_levels:
            metadata["top_levels"] = top_levels

        return metadata


def get_metadata_dict(path):
    parser = Parser()
    result = {}
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

    result = {runez.snakified(k, normalize=str.lower): v for k, v in result.items()}
    return result


@runez.click.command()
@click.option("--python", "-p", default=CURRENT_PY, help=f"Python interpreter to use (default: {CURRENT_PY})")
@click.argument("package", default=".")
def main(python, package):
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
    if package.startswith((".", "/", "~")):
        package = runez.resolved_path(package)

    metadata = get_metadata(package, python)
    print(runez.represented_json(metadata))
