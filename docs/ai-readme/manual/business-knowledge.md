# Business Knowledge

## Project context

Windows desktop wrapper around a local Prometheus checkout. It does not vendor Prometheus. The user supplies the checkout and a Lua interpreter.

<!-- TODO: human to fill: who the release is for, and whether the repository is public. -->

## Domain terms

| Term | Code name | Meaning |
| --- | --- | --- |
| Checkout | `prometheus_cli` | Directory that contains root `cli.lua` and `src/` |
| Spot check | `CHECKOUT_FILES` | Three files the launcher requires before it will run |
| Preset | `PRESETS` | Minify, Weak, Medium, Strong |
| Credit line | `build_credit` | UTC comment prepended to a successful output file |

## Business rules

- Attribution shown in the window and README: `Based on Prometheus by Elias Oelschner, https://github.com/prometheus-lua/Prometheus`
- Upstream license does not require that notice inside generated obfuscated files. The launcher adds a separate credit comment anyway.
- No installer. The `.exe` is an extra desktop entrypoint for a GitHub Release asset.
- This repository does not pin an application version.

<!-- TODO: human to fill: license of this launcher itself. Do not treat the Prometheus License as this repo's license unless the maintainer says so. -->
