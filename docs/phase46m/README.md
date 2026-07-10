# Phase 46M — Operator Portal Autonomous Campaign Controls

The operator portal receives a shell-safe service and FastAPI router for
campaign status, event history, start, pause, resume, and cancellation.

Campaign execution requires explicit protected-action approval. The portal
passes structured argv with `shell=False`; arbitrary shell text is forbidden.
