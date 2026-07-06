# Portal Local Deployment Guide

Portals are offline HTML files.

Open these files in a browser:

```text
workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_generation_progress_portal.html
workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_agent_runtime_portal.html
workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_self_correction_portal.html
```

Regenerate portals:

```bash
python scripts/generate_phase13b_progress_portal.py
python scripts/generate_phase13c_agent_runtime_portal.py
python scripts/generate_phase13c_self_correction_portal.py
```
