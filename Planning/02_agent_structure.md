# Step 3 — Specialized Agents & Project Plan Division
**Builds on:** `01_project_outline.md` (scope + architecture decisions)

---

## 1. Agent Roster

| Agent | Owns |
|---|---|
| **PM Agent** | Milestones, cross-agent dependencies, progress tracking, go/no-go decisions |
| **Backend Agent** | FastAPI, DB schema, budget engine logic, Supabase integration |
| **Frontend Agent** | Flutter app (mobile + web), all UI/UX, state management, API client |
| **DevOps/Infra Agent** | Supabase project setup, Render deploys, CI/CD, env/secrets |
| **QA/Testing Agent** | Test plans, unit/integration/e2e tests, bug tracking, production-readiness sign-off |

Five agents is intentionally lean — enough separation of concerns that each agent has a clean, ownable slice, without so many handoffs that coordination overhead outweighs the benefit. Database schema stays with the Backend Agent rather than a separate "data agent," since schema and API are tightly coupled in FastAPI + SQLAlchemy work.

---

## 2. PM Agent — Responsibilities

- Maintains this document and `01_project_outline.md` as living references.
- Breaks work into milestones (below) and tracks task status per agent.
- Owns the **API contract** as the critical dependency point between Backend and Frontend (see Section 4) — makes sure it's published early enough that Frontend isn't blocked waiting on full backend completion.
- Runs a check-in at the end of each milestone: confirms deliverables met, surfaces blockers, decides whether to proceed to the next milestone or loop back.
- Escalates any blocker or scope question to the user rather than resolving it unilaterally.
- Owns the final call — jointly with QA Agent and user — on whether the app is ready to leave Step 4 (Testing) and enter Step 5 (Production Infra).

---

## 3. Agent Deliverables

### Backend Agent
- Postgres schema (via Supabase): `categories`, `transactions`, `budgets` (users handled by Supabase Auth)
- FastAPI endpoints: transaction CRUD, category CRUD, monthly summary, budget suggestion
- Budget engine module: weighted 3-month rolling average, outlier trimming, **separate Essentials / Discretionary totals**
- All money fields as `Decimal`, never `float`
- Supabase Auth token verification middleware
- Publishes OpenAPI contract early (can stub endpoint shapes before logic is complete, so Frontend can build against it)

### Frontend Agent (Flutter)
- App shell — single codebase, responsive for mobile + web
- Onboarding: Supabase Auth signup/login, cold-start income input flow
- Quick transaction entry (target: <10 sec, ≤4 taps)
- Category management (create/edit/archive, essential/discretionary toggle)
- Monthly dashboard: income/expense/net, category breakdown chart, Essentials vs. Discretionary budget view
- API client layer built against Backend's published contract
- State management approach — recommend **Riverpod** (more testable, less boilerplate than Provider, well-suited to an app with real business logic like budget calculations reflected in UI state)

### DevOps/Infra Agent
- Supabase project setup (Postgres + Auth), dev/staging/prod environment separation
- Render service + CI/CD (auto-deploy on merge, secrets/env management) — hosts **both** the FastAPI backend and the compiled Flutter web build (static site), keeping DevOps to one vendor/dashboard alongside Supabase
- Basic error tracking/monitoring (recommend Sentry — free tier covers MVP scale) — flagging as a recommended addition, your call whether to include
- Mobile app store build/signing pipeline — deferred to Step 5/6, not needed until we're close to launch

### QA/Testing Agent
- Test plan covering: unit tests (budget math correctness, `Decimal` precision), API integration tests, Flutter widget tests, end-to-end flows (onboarding → add transaction → dashboard → budget generation)
- Bug tracking process
- Gatekeeper role for Step 4 sign-off, per your Step 4 definition: back-and-forth with PM Agent and you until everyone agrees the app is production-reliable

---

## 4. Coordination Model

**Critical dependency:** Backend ↔ Frontend, bridged by the OpenAPI contract. To avoid Frontend sitting idle waiting on Backend:
1. Backend Agent defines and publishes endpoint shapes (request/response schemas) before full business logic is implemented.
2. Frontend Agent builds against that contract using stub/mock responses.
3. Both agents integrate against the real backend once logic lands — this should be a fast swap, not a rebuild, if the contract didn't change.

**Milestones** (each ends with a PM Agent check-in before moving on):

| Milestone | Backend | Frontend |
|---|---|---|
| **M1 — Skateboard** | Auth wiring, basic transaction CRUD | Auth screens, transaction entry |
| **M2 — Categories & Monthly View** | Category CRUD, monthly summary endpoint | Category management UI, monthly dashboard |
| **M3 — Budget Engine** | Budget suggestion endpoint (cold-start + 3-month engine, essentials/discretionary split) | Budget input (cold-start), budget display/edit UI |
| **M4 — Polish & Edge Cases** | Error handling, validation hardening | Empty states, loading states, input validation |

After M4, QA Agent runs the full test plan and we move into Step 4 proper.

---

*Next step: hand off to the agents to start M1, with the PM Agent tracking progress.*
