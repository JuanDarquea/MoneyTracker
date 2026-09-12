# Step 5 — Production Infrastructure Preparation
**Builds on:** `01_project_outline.md`, `02_agent_structure.md`, `03_testing_strategy.md`

---

## 1. Environment Promotion Path

Dev → Staging → Production, as separate Supabase projects and separate Render services per stage, each with its own env vars. Code promotes stage by stage — nothing deploys straight to production. DevOps Agent owns this pipeline.

## 2. Domain & SSL — **DECIDED: needs registering**

- Need a custom domain for the web app and API (e.g. `app.yourdomain.com`, `api.yourdomain.com`)
- Render issues automatic SSL/TLS certs for custom domains — no extra setup burden
- **Action item (DevOps Agent):** register a domain before staging/production environments go live. Any mainstream registrar works fine (Namecheap, Cloudflare Registrar, Squarespace Domains) — happy to help brainstorm name options once you're ready for that conversation

## 3. Secrets & Config Management

- Supabase keys and Render env vars kept out of source control, scoped per environment
- Dev/test keys rotated to real production keys before go-live — never reused

## 4. Backups & Disaster Recovery

- Supabase provides automated daily Postgres backups on paid tiers — needs confirming our plan tier includes this (free tier has limited/no point-in-time recovery)
- A basic recovery runbook: documented steps for what to do if data is lost or corrupted

## 5. Monitoring & Alerting

- Sentry for error tracking (flagged in Step 3, confirming inclusion here)
- Render's built-in health checks
- Lightweight uptime monitor (e.g. UptimeRobot free tier) pinging the API health endpoint

## 6. Security Hardening

- CORS locked to the app's actual domains only
- Rate limiting on auth endpoints (brute-force protection)
- Dependency vulnerability scanning (GitHub Dependabot for both Python and Dart/Flutter deps)
- HTTPS enforced everywhere (Render handles this by default)

## 7. Legal & Compliance Basics — **DECIDED: I'll help draft**

- Privacy Policy and Terms of Service — required for an app handling financial data, and required by both app stores regardless of app category
- Scope: standard baseline disclosures (what data is collected, how it's stored, no data-sharing with third parties) — **not** claiming to be a licensed financial institution or offering financial advice
- **Action item:** I'll help draft both documents — best done as its own focused task once we have concrete details (legal business name/entity if any, jurisdiction, actual data practices from the finished app), so plan on tackling this as a dedicated step before the launch checklist below is fully checked off

## 8. Mobile App Store Preparation — **DECIDED: fast-follow after web launch**

- Web launches first (Step 6); mobile app stores follow shortly after, not on day 1 — avoids app-store review time (can take days) sitting on the critical path to launch
- Apple Developer account ($99/yr) + Google Play Developer account ($25 one-time)
- Store listing assets: screenshots, description, privacy policy link, app icon
- Review guideline compliance — financial apps get extra scrutiny (clear data handling disclosure, no misleading budget/savings claims)

## 9. Launch Readiness Checklist (rolls into Step 6)

**Web launch (Step 6):**
- [ ] All Step 4 sign-off criteria met
- [ ] Production environment provisioned & smoke-tested
- [ ] Domain registered, + SSL live
- [ ] Backups verified working (test a real restore, not just "backups exist")
- [ ] Monitoring/alerts active
- [ ] Privacy Policy & Terms of Service drafted and published

**Mobile fast-follow (post-launch):**
- [ ] Apple + Google developer accounts set up
- [ ] Store listings submitted
- [ ] App store review passed

---

## 10. Decisions

1. **Domain name** — needs registering (action item above).
2. **Legal docs** — drafting Privacy Policy/ToS together, as a dedicated task.
3. **Mobile app store timing** — web-first; app stores are a fast-follow, not part of day-1 launch.

---

*Next step: register the domain, then move into Step 6 (Launch) for the web app, with mobile app stores tracked as the first fast-follow item after that.*
