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
