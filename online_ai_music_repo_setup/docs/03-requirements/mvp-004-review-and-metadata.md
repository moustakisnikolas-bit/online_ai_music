# MVP-004: Review and Metadata

## Objective

Ensure generated assets can be reviewed before future publishing and can receive a safe, platform-neutral metadata package.

## Review States

- pending
- approved
- rejected

## Rules

- Only completed jobs can be approved.
- Only completed jobs can be rejected.
- Publishing integrations must require `approved`.
- Review decisions may include a reason.
- Review actions must later be added to the audit log.

## Metadata Package

The generated package includes:

- title;
- subtitle;
- description;
- keywords;
- category;
- language;
- compliance note.

## Language Safety

Metadata must not claim:

- disease treatment;
- DNA repair;
- toxin removal;
- guaranteed neurological results;
- replacement of medical care.
