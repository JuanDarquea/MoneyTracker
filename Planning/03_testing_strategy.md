# Step 4 — Testing Strategy
**Builds on:** `01_project_outline.md`, `02_agent_structure.md`

---

## 1. Testing Philosophy & Loop

Testing runs **alongside** development, not after it — the QA Agent tests each milestone's deliverables as they land (M1–M4 from Step 3), rather than everything piling up at the end.

The loop: QA Agent tests → files bugs → owning agent (Backend/Frontend/DevOps) fixes → QA re-verifies → PM Agent updates the shared bug/status board → repeat until the Section 5 sign-off criteria are met. This is the "back and forth" cycle you described — it can run as many passes as needed, there's no fixed number.

---

## 2. Test Layers & Tooling

| Layer | Scope | Tooling | Built by |
|---|---|---|---|
| Unit tests | Budget engine math, `Decimal` precision, validation logic | pytest | Backend Agent, verified by QA |
| API integration tests | Every FastAPI endpoint — happy path + edge cases + auth failures | pytest + httpx | QA Agent |
| Widget tests | Individual Flutter UI components | flutter_test | Frontend Agent, verified by QA |
| End-to-end tests | Full user flows on the real app | Flutter `integration_test` | QA Agent |
| Manual QA / UAT | Exploratory testing — "does this actually feel right to use" | Manual, checklist-driven | QA Agent + You |
| Beta round | Short real-user UAT round after QA's own pass clears, before Step 5 | Manual, small group of real test users | PM Agent coordinates, QA Agent collects feedback |

---

## 3. Critical Test Scenarios (mapped to MVP features)

- **Auth:** signup, login, logout, invalid credentials, session expiry
- **Transactions:** add/edit/delete income & expense; validation (negative amounts, missing category, decimal precision — e.g. rounding on 19.995)
- **Categories:** create/edit/archive; essential/discretionary tagging; a category can't mix income and expense
- **Monthly tracking:** correct aggregation across month boundaries; edge case of a transaction logged right at midnight/month-end
- **Budget engine:**
  - Cold-start path (<3 months history) — manual income input
  - 3-month+ path — auto-suggested budget, weighted average computed correctly
  - Outlier trimming — a single large one-off expense should not blow up a category's suggested budget
  - Essentials vs. Discretionary — correctly separated, each with its own total
- **Cross-platform parity:** core flows re-verified on both the mobile build and the web build — Flutter renders once, but platform-specific quirks (touch vs. mouse, screen size) still need a pass on each

---

## 4. Bug Severity & Triage

| Severity | Definition | Blocks sign-off? |
|---|---|---|
| Critical | Data loss, incorrect money math, auth/security bypass | Yes — fixed immediately, everything else pauses |
| High | Core flow broken (can't add a transaction, budget engine crashes) | Yes |
| Medium | UI bugs, non-blocking edge cases | Fixed if time allows; otherwise fast-follow list |
| Low | Cosmetic | Backlog, doesn't block launch |

PM Agent owns the bug board and re-runs the same check-in pattern used for milestones in Step 3 — confirm status after each fix pass before moving forward.

---

## 5. Production-Readiness Sign-off Criteria

The app moves to **Step 5 (Production Infrastructure)** only when **all** of the following hold:

- Zero open Critical or High severity bugs
- All Section 3 scenarios passing on both mobile and web builds
- Money math spot-checked by hand on a sample of test transactions — a human sanity check on top of automated tests, given this is financial data
- Beta round complete, with no Critical/High severity issues surfaced by test users
- QA Agent, PM Agent, **and you** all explicitly sign off

---

## 6. Decisions

1. **Backend test coverage target — 90%+ on business logic** (budget engine, money math, validation). Non-negotiable given this is financial data. UI/widget test coverage stays looser at MVP stage.
2. **Short beta/UAT round with a few real test users**, run after the QA Agent's own pass (Sections 3–4) clears and before Step 5. Added as its own layer below.

---

*Next step: QA Agent begins testing against M1 deliverables as they land, following the loop in Section 1.*
