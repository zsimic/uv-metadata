# uv-metadata

Python proof-of-concept implementation of a `uv metadata` subcommand

The script uses std lib only, so you should be able to easily try it out.
You need `uv` available on `PATH`.

The intent is to provide metadata information on a single python package,
given a PEP-508 compliant spec.

Examples:

- Info on a published package

```shell
~: uv-metadata requests
{
    "author": "Kenneth Reitz",
    ...
    "name": "requests",
    "requires_dist": [
        "charset_normalizer<4,>=2",
        ...
    "requires_python": ">=3.9",
    "version": "2.32.5"
}

~: uv-metadata 'requests<2'
{
    ...
    "version": "1.2.3"
}
```

- Info on a git folder:

```
~: uv-metadata git+https://github.com/zsimic/uv-metadata@main
{
    "entry_points": {
        "console_scripts": {
            "uv-metadata": "uv_metadata:main"
        }
    },
    "license_file": "LICENSE",
    "metadata_version": "2.4",
    "name": "uv-metadata",
    "top_level": [
        "uv_metadata"
    ],
    "version": "0.1.0"
}
```


- Info on a local folder

```
~: uv-metadata .
{
    ...
    "name": "...",
    "version": "..."
}
```
