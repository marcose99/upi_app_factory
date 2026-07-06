# Governance, Audit, and Self-Correction Guide

Every warning and error must be handled.

Required decision states:
- auto_remediate
- plan_only
- human_approval_required
- blocked
- no_change_needed

Auto-remediable examples:
- formatting
- lint
- import path
- test fixture
- portal population
- documentation gap
- validator message
- low-risk generated app fix

Human approval required:
- git release
- dependency installation
- security-policy weakening
- tool-authorization expansion
- destructive reset
- regulatory claim wording
- live integration
- customer data handling
- quality objective waiver

Blocked:
- real payment execution
- real customer data use
- false compliance claim
- credential exposure

Release rule:
- no handover/release/freeze should happen with untriaged warnings or errors.
