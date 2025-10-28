import os
import shutil
import subprocess
import sys
import tempfile

import click


def abort(msg: str):
    sys.exit(msg)


def run_command(exe, *args):
    exe = shutil.which(exe)
    description = "%s %s" % (exe, " ".join(args))
    print(f"Running: {description}")
    full_cmd = [exe, *args]
    result = subprocess.run(full_cmd, capture_output=True, text=True, check=False)
    return result


def get_metadata(pip_spec: str) -> dict:
    with tempfile.TemporaryDirectory() as tmpdirname:
        os.chdir(tmpdirname)
        run_command("uv", "venv", "-p3.14")
        run_command("uv", "pip", "install", "--no-deps", pip_spec)
        r = run_command("uv", "pip", "freeze")
        lines = r.stdout and r.stdout.strip().splitlines()
        if not lines or len(lines) != 1:
            abort(f"'pip freeze' for '{pip_spec}' failed: {r.stdout}\n{r.stderr}")


@click.command()
@click.argument("package", default=".")
def main(package):
    # Ensure we don't let our own venv interfere with uv usage
    os.environ.pop("VIRTUAL_ENV", None)
    os.environ["UV_VENV_SEED"] = "0"
    print(get_metadata(package))
