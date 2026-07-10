# Phase 46K — Repository-Native Autonomous Supervisor

Phase 46K productizes the proven external autonomous supervisor as a permanent
factory capability.

Permanent command:

```bash
./bin/upi-app-factory-autonomous run \
  config/autonomous_campaigns/autonomy_productization_46l_46n.json \
  --approve commit,merge,push \
  --resume \
  --project-root .
```

The supervisor observes campaign state, classifies failures, provisions
hash-pinned ignored evidence, restores approved runtime noise, applies only
catalogued low-risk repairs, invalidates stale lifecycle evidence, resumes the
same run, and progresses to the next phase.

Unknown semantic failures fail closed with incident evidence. Tag, release,
production deployment, physical checkout rename, remote repository rename,
legacy alias retirement, and official certification remain human-controlled.
