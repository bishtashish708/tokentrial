# Configuration

Settings are grouped in sections (`service`, `http`, `queue`, `worker`, `sink`, `logging`)
and addressed as `section.name`, e.g. `worker.count`. The full list with defaults is in
`ingestd/config/defaults.py`.

## Layers

Settings are resolved from several layers; a later layer overrides an earlier one:

1. built-in defaults
2. the main config file (`config/ingestd.conf`, or `--config` / `INGESTD_CONFIG`),
   together with any files it `@include`s
3. the profile file `profiles/<profile>.conf` next to the main config file
4. `local.conf` next to the main config file, if present (not checked in)
5. environment variables
6. command-line options

After all layers are merged some values are validated and adjusted; see
`ingestd/config/finalize.py`.

## Config files

INI-like: `[section]` headers and `key = value` lines; `#` and `;` start comments.
`@include <pattern>` reads other files (glob patterns allowed, relative to the including
file) at that point of the file.

## Sizes

Settings ending in `_bytes` accept a plain number of bytes or a number with a unit:
`k`/`KB` (1000), `KiB` (1024), `M`/`MB`, `MiB`, `G`/`GB`, `GiB`.

## Environment variables

`INGESTD_<SECTION>__<NAME>` (double underscore) sets `section.name`, e.g.
`INGESTD_WORKER__COUNT=4`. `INGESTD_CONFIG` and `INGESTD_PROFILE` choose the config file
and profile. A few older names are still accepted for compatibility (see
`ingestd/config/env.py`); setting both an old and a new name logs a warning.

## Deprecated keys

Renamed keys are still read and translated to their new names, with a warning. See
`ingestd/config/deprecations.py`.
