
# Help synopsis

```
~: uv metadata --help
Output metadata info about specified package, in machine readable format

Usage: uv metadata [OPTIONS] [PACKAGE]

Arguments:
  [PACKAGE]  PEP-508 specification of python package (default: current folder)

Options:
  -k, --key <KEY>        If specified, show only the value of specified <KEY>

... 8< ... rest of uv's global options
```


```
~: uv help metadata
Output metadata info about specified package, in machine readable format.

By default, show metadata of python project in current working directory.

Usage: uv metadata [OPTIONS] [PACKAGE]

Arguments:
  [PACKAGE]
          PEP-508 specification of python package to show metadata for.

Options:
      -k, --key
          When specified, show only the value of that key
```
