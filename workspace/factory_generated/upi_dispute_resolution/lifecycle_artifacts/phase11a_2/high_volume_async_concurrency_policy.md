# High-Volume, Async, Concurrency, and Parallelism Policy — upi_dispute_resolution

Labels: HIGH_VOLUME_ENGINEERING_REQUIRED, ASYNC_CONCURRENCY_REQUIRED,
DETERMINISTIC_VALIDATION_REQUIRED, FAIL_CLOSED

Generated designs must support high-volume local simulation while remaining safe
on a laptop.

Required engineering patterns:

- bounded async queues for intake and worker paths
- configurable worker counts
- concurrency limits
- idempotency keys
- deduplication
- pagination
- chunked processing
- streaming-style file reads where useful
- retry with capped exponential backoff
- timeouts
- circuit breakers
- bulk validation
- deterministic replay tests
- load-shape configuration for local runs

Do not introduce unbounded threads, unbounded tasks, unbounded queues, or
unbounded memory growth.
