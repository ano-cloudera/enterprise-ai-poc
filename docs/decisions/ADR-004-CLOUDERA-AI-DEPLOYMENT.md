# ADR-004: Cloudera AI Application as Primary Deployment

**Status:** Accepted  
**Date:** 2026-10-13

## Context

Product goal is reusable PoC/Pilot on customer CDP/CAI environments.

## Decision

Primary packaging:

- **Backend** CAI Application → `app_cai_backend.py` / uvicorn
- **Frontend** CAI Application → Next.js build + proxy to backend
- Environment via CAI secrets + repo `.env.example` templates

Impala/Trino connectivity uses customer cluster credentials (Kerberos/LDAP).

## Consequences

- Reuse existing Tempo Scan deployment docs as templates
- Health endpoints required for CAI probes
- CORS and `/api` rewrite pattern mandatory for browser clients

## Not in scope

Multi-region HA, autoscaling policies, service mesh
