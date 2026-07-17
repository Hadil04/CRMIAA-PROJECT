# TODO — RBAC for CRMIAA

- [ ] Add `role_required()` decorator (keep session-based auth) in `app/utils/decorators.py`
- [ ] Update login redirect logic in `app/auth/routes.py`:
  - Admin -> `/admin/dashboard`
  - User -> `/user/dashboard`
- [ ] Update `/` routing in `app/main/routes.py` to redirect based on `session['role']`
- [ ] Create `app/user` blueprint + `/user/dashboard` protected by `login_required` + `role_required('User')`
- [ ] Register the new blueprint in `app/__init__.py`
- [ ] Protect admin dashboard with `role_required('Admin')`
- [x] Implement admin-only access + role_required decorator
- [ ] Implement admin users management page and actions:


  - [ ] Add `GET /admin/users` (list users)
  - [ ] Add `POST /admin/users/<id>/toggle-role` (Promote to Admin / Demote to User)
  - [ ] Add `POST /admin/users/<id>/disable` (Disable user)
  - [ ] Implement “last active admin” safety rule
  - [ ] Add template `app/templates/admin/users.html`
- [ ] Update `app/templates/base.html` to display current user's role in navigation/header
- [ ] Update `README.md` with RBAC/decorator conventions for future routes
- [ ] Run a quick sanity check: import app, ensure routes render without template errors

