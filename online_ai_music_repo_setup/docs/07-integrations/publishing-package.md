# Platform-Neutral Publishing Package

## Purpose

The current catalog metadata is platform-neutral.

It can later be transformed into:

- YouTube title and description;
- distributor release metadata;
- Apple Music metadata;
- Amazon Music metadata;
- website content;
- social media copy.

## Current Scope

No automatic publishing occurs.

The current implementation prepares metadata and requires human review.

## Future Publishing Gate

A publishing adapter must verify:

1. the audio job completed;
2. the asset exists;
3. metadata exists;
4. review status is approved;
5. platform credentials are available;
6. platform-specific validation passes.
