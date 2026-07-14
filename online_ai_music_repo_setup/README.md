# online_ai_music Repository Setup

This package bootstraps the GitHub repository:

`https://github.com/moustakisnikolas-bit/online_ai_music.git`

The GitHub repository was empty when this package was prepared.

## Recommended use

```bash
unzip online_ai_music_repo_setup.zip
cd online_ai_music_repo_setup
chmod +x *.sh bootstrap/*.sh bootstrap/lib/*.sh
./01-clone-and-bootstrap.sh
```

This will:

1. clone the repository into `./online_ai_music`;
2. generate the AION repository structure;
3. validate the generated files;
4. leave all changes uncommitted for your review.

## Review and commit

```bash
cd online_ai_music
git status
git add .
git commit -m "Bootstrap AION documentation and repository structure"
git push -u origin main
```

## Automated commit, without push

```bash
AUTO_COMMIT=1 ./01-clone-and-bootstrap.sh
```

## Automated commit and push

Use only after reviewing the package:

```bash
AUTO_COMMIT=1 AUTO_PUSH=1 ./01-clone-and-bootstrap.sh
```

GitHub authentication must already be configured on your computer.

## Existing local clone

Run:

```bash
./02-bootstrap-existing-clone.sh /full/path/to/online_ai_music
```

## Dry run

```bash
DRY_RUN=1 ./01-clone-and-bootstrap.sh
```

The scripts do not overwrite existing non-empty files unless `FORCE=1` is explicitly supplied.
