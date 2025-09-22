# Data Model (Conceptual)

## Entities

### User
- Attributes: id, email, displayName, passwordHash (implementation detail deferred), roles (optional)
- Relationships: has many Sessions
- Notes: Email unique; validation rules apply.

### Session
- Attributes: token/id, userId, createdAt, expiresAt, lastActivityAt
- Relationships: belongs to User
- Notes: Sliding expiry considered; for MVP, fixed 8 hours.

## Validation Rules
- Email must be valid and unique.
- Password must meet minimum complexity (length >= 8) [policy TBD].
- Session expiry must be enforced on backend; frontend should react to 401/403.

## States & Transitions (Auth)
- Unauthenticated → Login success → Authenticated (session created)
- Authenticated → Logout → Unauthenticated (session cleared)
- Authenticated → Expiry → Unauthenticated (redirect to login with message)
