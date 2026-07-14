# MVP-002: Persistent Audio Jobs

## Objective

Move audio generation from a synchronous request into a persistent queue-backed workflow.

## Functional Requirements

- Create projects.
- Submit audio jobs.
- Persist job state in PostgreSQL.
- Queue work in Redis.
- Process jobs in a worker.
- Retrieve job status.
- List recent jobs.
- Store output file paths.
- Preserve errors for diagnosis.

## Job States

- queued
- queue_failed
- processing
- completed
- failed

## Acceptance Criteria

1. An audio job receives a persistent UUID.
2. The API returns HTTP 202 for accepted jobs.
3. The worker updates the job to processing.
4. Successful completion stores an output path.
5. Failures store an error message.
6. Duplicate worker pickup does not process terminal jobs again.
