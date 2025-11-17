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
    "author_email": "me@kennethreitz.org",
    "classifier": [
        "Development Status :: 5 - Production/Stable",
        ...
    ],
    "description_content_type": "text/markdown",
    "home_page": "https://requests.readthedocs.io",
    "license": "Apache-2.0",
    "license_file": "LICENSE",
    "metadata_version": "2.4",
    "name": "requests",
    "project_url": [
        "Documentation, https://requests.readthedocs.io",
        "Source, https://github.com/psf/requests"
    ],
    "provides_extra": [
        "security",
        "socks",
        "use-chardet-on-py3"
    ],
    "requires_dist": [
        "charset_normalizer<4,>=2",
        ...
    "requires_python": ">=3.9",
    "summary": "Python HTTP for Humans.",
    "top_level": [
        "requests"
    ],
    "version": "2.32.5"
}

~: uv-metadata 'requests<2'
{
    ...
    "version": "1.2.3"
}
```

- Project from git url:

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


- Project in a local folder

```
~: uv-metadata .
{
    ...
    "name": "my-project",
    "version": "0.1.0"
}
```


Relevant PEPs:

- [PEP 508](https://peps.python.org/pep-0508/) – Dependency specification for Python Software Packages
- [PEP 241](https://peps.python.org/pep-0241/) – Metadata for Python Software Packages
- [PEP 314](https://peps.python.org/pep-0314/) – Metadata for Python Software Packages 1.1
- [PEP 345](https://peps.python.org/pep-0345/) – Metadata for Python Software Packages 1.2
- [PEP 426](https://peps.python.org/pep-0426/) – Metadata for Python Software Packages 2.0
- [PEP 566](https://peps.python.org/pep-0566/) – Metadata for Python Software Packages 2.1
- [PEP 643](https://peps.python.org/pep-0643/) – Metadata for Package Source Distributions
- [PEP 685](https://peps.python.org/pep-0685/) – Comparison of extra names for optional distribution dependencies
- [PEP 639](https://peps.python.org/pep-0639/) – Improving License Clarity with Better Package Metadata

`pkginfo` has a nice
[overview](https://github.com/jwilk-mirrors/python-pkginfo/blob/master/pkginfo/distribution.py#L34)
of what fields were introduced when.


# Help synopsis

- `uv metadata --help`

```
Output metadata info about specified package, in machine readable format

Usage: uv metadata [OPTIONS] [PACKAGE]

Arguments:
  [PACKAGE]  PEP-508 specification of python package (default: current folder)

Options:
  -k, --key <KEY>        If specified, show only the value of specified <KEY>

... 8< ... rest of uv's global options
```

- `uv help metadata`

```
Output metadata info about specified package, in machine readable format.

By default, show metadata of python project in current working directory.

Usage: uv metadata [OPTIONS] [PACKAGE]

Arguments:
  [PACKAGE]
          PEP-508 specification of python package to show metadata for.

Options:
      -k, --key
          When specified, show only the value of that key

... 8< ... rest of uv's global options
```
