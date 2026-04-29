# RBAC permission matrix (P0-4)

Roles:
- admin
- manager
- supplier
- service
- buyer

Sensitive API policy:

1) /api/v1/admin/*
- allow: admin, manager
- deny: supplier, service, buyer

2) /api/v1/supplier/*
- allow: supplier, admin
- deny: service, buyer

3) /api/v1/service/*
- allow: service, admin
- deny: supplier, buyer

4) /api/v1/integration/*
- allow: authenticated users (current policy)
- note: provider health / technical ops can be hardened to admin-only in next step

Validation status:
- role guards implemented via `require_roles` for admin/supplier/service modules
- syntax/compile checks for modified modules passed
- endpoint-level automated tests: pending
