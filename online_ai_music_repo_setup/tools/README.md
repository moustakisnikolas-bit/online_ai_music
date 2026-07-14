# AION Tools

## CLI

The AION CLI generates consistent repository artifacts.

```bash
./tools/aion/aion help
./tools/aion/aion version
./tools/aion/aion doctor
```

## Generators

```bash
./tools/aion/aion generate service audio-engine
./tools/aion/aion generate adr use-postgresql
./tools/aion/aion generate workflow publish-youtube
./tools/aion/aion generate doc architecture storage-strategy
```

## Safety

Generators refuse to overwrite existing files.

Use `--force` only after reviewing the existing artifact:

```bash
./tools/aion/aion generate workflow publish-youtube --force
```

## Naming

Names must use lowercase letters, numbers and single hyphens.
