# AION Bootstrap Scripts

This package creates the initial repository structure for the **AION - AI Autonomous Content Operating System**.

## Requirements

- macOS or Linux
- Bash 4+ recommended
- Git
- Optional: Docker, Docker Compose, Python 3, Node.js, Make

## Installation

Extract the ZIP, open a terminal inside the extracted folder, and run:

```bash
chmod +x *.sh lib/*.sh
./00-bootstrap-aion.sh
```

By default, the scripts operate on the current directory.

To target another directory:

```bash
AION_ROOT="/path/to/aion-os" ./00-bootstrap-aion.sh
```

## Safety

The scripts:

- do not delete project files;
- do not overwrite existing non-empty files unless explicitly requested;
- create a timestamped log under `.aion/logs`;
- can be run repeatedly;
- support `DRY_RUN=1`.

Example:

```bash
DRY_RUN=1 ./00-bootstrap-aion.sh
```

## Script Order

1. `00-bootstrap-aion.sh`
2. `01-init-git.sh`
3. `02-create-repository-structure.sh`
4. `03-create-governance-docs.sh`
5. `04-create-product-docs.sh`
6. `05-create-architecture-docs.sh`
7. `06-create-ai-context.sh`
8. `07-create-service-templates.sh`
9. `08-create-infrastructure.sh`
10. `09-create-testing-quality.sh`
11. `10-create-github-automation.sh`
12. `11-validate-repository.sh`

The bootstrap script invokes the remaining scripts automatically.
