"""The corpus and golden query set behind `evals/retrieval_eval.py`.

Separated from the harness because it is data, not logic, and because it is the
part that should grow. The metrics code is finished; this file never is.

## Why a synthetic corpus

A retrieval eval needs a fixed corpus with known answers. Real uploaded customer
documents cannot go in the repository, and a public dataset (MS MARCO, BEIR)
would measure retrieval over web prose — the exact mismatch that made the first
`RAG_MIN_RERANK_SCORE` default wrong. So the corpus below is written to read like
what this application actually ingests: internal business reviews, product
documentation, competitive briefs, research synthesis, security questionnaires.
Dense paragraphs of specifics, the way a real PDF page reads.

Two properties are deliberate and matter more than the volume:

1. **Near-miss chunks exist.** For most queries the corpus contains a chunk on
   the same subject that does not answer the question — churn numbers vs. NPS
   survey logistics, rate limits vs. latency. A corpus of unrelated chunks makes
   any retriever look good, because ranking is trivial when only one chunk is
   even topical.
2. **Some answers need vocabulary the query does not use.** Queries like "how
   long until an enterprise deal closes" never say "sales cycle". Those are what
   dense retrieval is for. Others hinge on an exact token — `ACM-429`, `SCIM`,
   `AES-256` — which is what the lexical half is for. Both are labelled below so
   a regression in either half is visible rather than averaged away.

## Grades

`relevant` chunks answer the query; `partial` chunks are genuinely useful
context that does not answer it. Hit rate and MRR count only `relevant` — the
question they ask is "did retrieval surface something that answers this?", and
crediting a partial chunk for that would flatter the pipeline. NDCG uses both,
with gains 2 and 1, because ordering a partial chunk above an irrelevant one is
a real improvement that the binary metrics cannot see.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    page: int
    text: str


@dataclass(frozen=True)
class Golden:
    query: str
    relevant: tuple[str, ...]
    partial: tuple[str, ...] = ()
    # Free-text tag for slicing the report: what this query is meant to exercise.
    kind: str = "lookup"


# ── corpus ───────────────────────────────────────────────────────────────────

CORPUS: list[Chunk] = [
    # ── acme_q3_business_review.pdf ──────────────────────────────────────────
    Chunk(
        "biz-arr", "acme_q3_business_review.pdf", 2,
        "Annual recurring revenue closed the quarter at $16.4M, up from $11.9M a "
        "year earlier, a growth rate of 38%. New business contributed $3.1M of "
        "the increase and expansion within the existing base $1.9M, offset by "
        "$0.5M of contraction. The plan for the year assumed $17.2M, so the "
        "quarter finished 5% behind plan on the headline number.",
    ),
    Chunk(
        "biz-churn", "acme_q3_business_review.pdf", 2,
        "Gross logo churn in Q3 was 47 accounts against a starting base of "
        "1,210, or 3.9% for the quarter. Gross revenue churn was lower at 2.6%, "
        "because the accounts lost skewed to the smallest contracts. Net revenue "
        "retention held at 108%, with expansion in the mid-market segment "
        "offsetting the logo loss.",
    ),
    Chunk(
        "biz-pipeline", "acme_q3_business_review.pdf", 3,
        "Qualified pipeline entering Q4 stands at $9.8M against a $2.6M new "
        "business target, giving coverage of 3.8x. Coverage is thinnest in "
        "enterprise, at 2.4x, where three deals account for nearly half of the "
        "segment's weighted forecast. The team is treating that concentration as "
        "the single largest risk to the quarter.",
    ),
    Chunk(
        "biz-sales-cycle", "acme_q3_business_review.pdf", 3,
        "Enterprise deals average 94 days from first qualified meeting to "
        "signature, extending to roughly 140 days when a security review is "
        "required. Mid-market closes in 41 days and self-serve conversion "
        "happens inside a week. Deals with an executive sponsor identified in "
        "the first two weeks close 31% faster than those without one.",
    ),
    Chunk(
        "biz-loss-reasons", "acme_q3_business_review.pdf", 4,
        "Loss reasons recorded in the CRM cluster into three buckets: price "
        "(38%), missing SSO or compliance capability (27%), and an incumbent "
        "renewal that was never genuinely contestable (21%). The remaining 14% "
        "are recorded as no decision. Price losses are concentrated below $25k "
        "of annual contract value.",
    ),
    Chunk(
        "biz-launch-retro", "acme_q3_business_review.pdf", 5,
        "The Q2 launch slipped three weeks after load testing surfaced a "
        "connection-pool exhaustion bug under concurrent imports. Post-launch "
        "activation came in 22% below forecast. The retrospective attributed the "
        "shortfall to the onboarding flow rather than to the delay, on the "
        "grounds that trial starts recovered within a fortnight while completion "
        "rates did not.",
    ),
    Chunk(
        "biz-headcount", "acme_q3_business_review.pdf", 6,
        "The FY plan adds 34 roles, weighted to engineering (16) and go-to-market "
        "(12), with the balance in support and finance. Hiring is back-loaded "
        "into the second half and contingent on reaching $18M ARR by the end of "
        "Q2. Average fully loaded cost per engineering hire is modelled at "
        "$196,000.",
    ),
    Chunk(
        "biz-tam", "acme_q3_business_review.pdf", 7,
        "Management sizes the total addressable market at $14.2B, derived "
        "bottom-up from roughly 310,000 target companies at an average contract "
        "value of $46,000. The serviceable obtainable market over five years is "
        "put at $1.1B, assuming the current segment focus and no expansion into "
        "adjacent workflow categories.",
    ),
    Chunk(
        "biz-cac-payback", "acme_q3_business_review.pdf", 4,
        "Blended customer acquisition cost payback is 19 months, against a "
        "target of 15. Self-serve pays back in 7 months and mid-market in 16, "
        "while enterprise sits at 31 months and is what pulls the blended figure "
        "out. The magic number for the quarter was 0.7.",
    ),
    Chunk(
        "biz-segment-mix", "acme_q3_business_review.pdf", 5,
        "Revenue mix shifted further toward mid-market, which now represents 54% "
        "of ARR against 46% a year ago. Enterprise is 31% and self-serve 15%. "
        "The shift is deliberate — mid-market carries the best combination of "
        "contract value and sales efficiency — but it concentrates renewal risk "
        "in a segment with no dedicated success coverage.",
    ),
    Chunk(
        "biz-support-load", "acme_q3_business_review.pdf", 6,
        "Support handled 4,180 tickets in the quarter, up 31% year over year "
        "against 38% ARR growth, so load per dollar of revenue improved "
        "slightly. Median first response was 2.4 hours and 71% of tickets closed "
        "without escalation. Import and data-mapping questions remain the "
        "largest single category at 24% of volume.",
    ),
    Chunk(
        "biz-board-asks", "acme_q3_business_review.pdf", 8,
        "Three decisions are requested of the board this quarter: approval to "
        "open an EU data region ahead of the FY plan, a $400k increase to the "
        "security budget to bring penetration testing in-house, and sign-off on "
        "raising the self-serve price point by 20% in January.",
    ),

    # ── acme_platform_docs.pdf ───────────────────────────────────────────────
    Chunk(
        "doc-api-auth", "acme_platform_docs.pdf", 1,
        "The public API is REST over HTTPS and authenticates with OAuth 2.0 "
        "using the authorization code flow with PKCE. Access tokens live for one "
        "hour and refresh tokens for thirty days. A GraphQL endpoint is available "
        "in beta at /graphql and shares the same token scopes as the REST "
        "surface.",
    ),
    Chunk(
        "doc-webhooks", "acme_platform_docs.pdf", 2,
        "Webhooks support 14 event types. Deliveries are retried with "
        "exponential backoff for up to 24 hours, and every payload is signed "
        "with an HMAC-SHA256 signature in the X-Acme-Signature header that "
        "receivers must verify. Endpoints failing for seven consecutive days are "
        "disabled and the owner notified.",
    ),
    Chunk(
        "doc-rate-limits", "acme_platform_docs.pdf", 2,
        "Rate limits are 600 requests per minute per workspace on the REST API, "
        "with a burst allowance of 100. Exceeding the limit returns HTTP 429 "
        "with error code ACM-429 and a Retry-After header. Limits were tightened "
        "in June after a single tenant saturated a shared queue; enterprise "
        "workspaces may request a raised ceiling.",
    ),
    Chunk(
        "doc-sdks", "acme_platform_docs.pdf", 3,
        "Official SDKs ship for Python, TypeScript, and Go, and are generated "
        "from the OpenAPI description published at /openapi.json. Each SDK "
        "handles token refresh, retry, and pagination automatically. Community "
        "clients exist for Ruby and PHP but are not covered by support.",
    ),
    Chunk(
        "doc-residency", "acme_platform_docs.pdf", 4,
        "Customers may pin a workspace to the EU, US, or APAC region at "
        "provisioning time. The region cannot be changed afterwards without a "
        "migration request, which takes up to ten business days. Backups and "
        "search indexes never leave the selected region, though aggregate "
        "telemetry containing no customer content is processed in the US.",
    ),
    Chunk(
        "doc-retention", "acme_platform_docs.pdf", 4,
        "Activity logs are retained for 24 months by default, after which "
        "records are aggregated and the raw events discarded. Enterprise "
        "workspaces may configure a window of up to 7 years. Deleted records "
        "enter a 30-day soft-delete window before purge and can be restored by "
        "an administrator during that period.",
    ),
    Chunk(
        "doc-import", "acme_platform_docs.pdf", 5,
        "Bulk import accepts CSV and JSONL up to 500MB per file and 2 million "
        "rows per job. Column mapping is inferred from headers and can be "
        "overridden in the mapping step. Jobs run asynchronously and report "
        "per-row errors in a downloadable report; a job with more than 5% failed "
        "rows is halted for review rather than partially applied.",
    ),
    Chunk(
        "doc-sso", "acme_platform_docs.pdf", 6,
        "Single sign-on is available on the enterprise tier via SAML 2.0 and "
        "OIDC, with Okta, Entra ID, and Google Workspace validated. User "
        "provisioning and deprovisioning uses SCIM 2.0 against the /scim/v2 "
        "endpoint. Group membership can be mapped to workspace roles so that "
        "access follows the directory.",
    ),
    Chunk(
        "doc-audit-logs", "acme_platform_docs.pdf", 6,
        "Audit logs capture authentication, permission changes, data export, and "
        "administrative configuration events, each with actor, source IP, and "
        "timestamp. They are queryable in the admin console for 90 days and "
        "exportable to S3 or a SIEM over a streaming connector for longer "
        "retention.",
    ),
    Chunk(
        "doc-errors", "acme_platform_docs.pdf", 7,
        "Error responses carry a machine-readable code and a human-readable "
        "message. ACM-401 indicates an invalid or expired token, ACM-403 a scope "
        "the token does not hold, ACM-422 a validation failure with a field-level "
        "detail array, and ACM-503 a dependency outage that should be retried.",
    ),
    Chunk(
        "doc-versioning", "acme_platform_docs.pdf", 7,
        "API versions are dated, requested with the Acme-Version header, and "
        "supported for 18 months after a successor ships. Breaking changes never "
        "land in an existing version. Deprecations are announced in the changelog "
        "and surfaced in the Sunset response header at least 180 days before "
        "removal.",
    ),
    Chunk(
        "doc-sandbox", "acme_platform_docs.pdf", 3,
        "Every workspace gets a sandbox with an isolated dataset, its own API "
        "credentials, and no outbound webhook delivery. Sandbox data is reset on "
        "request and is never included in billing or usage counts. Rate limits in "
        "sandbox are a tenth of production so integrations surface throttling "
        "behaviour before launch.",
    ),

    # ── competitive_landscape_2026.pdf ───────────────────────────────────────
    Chunk(
        "comp-set", "competitive_landscape_2026.pdf", 1,
        "The competitive set divides cleanly by segment. Zapier dominates the "
        "SMB end on breadth of connectors, Workato and Tray.io contest "
        "mid-market on governance and error handling, and MuleSoft holds large "
        "enterprise integration programmes through its position with central IT. "
        "We compete directly with the middle two and displace the first.",
    ),
    Chunk(
        "comp-pricing", "competitive_landscape_2026.pdf", 2,
        "List pricing across the set is hard to compare because the units "
        "differ. Zapier meters tasks, Workato prices per recipe and connection, "
        "and MuleSoft sells capacity in vCores. Normalised to a mid-market "
        "workload of 2 million monthly operations, annual cost lands near $31k "
        "for Workato, $58k for MuleSoft, and $19k for us.",
    ),
    Chunk(
        "comp-zapier", "competitive_landscape_2026.pdf", 3,
        "Zapier's moat is its connector catalogue, which is roughly six times "
        "the size of ours and effectively impossible to match directly. Its "
        "weakness is operational: no meaningful version control, limited "
        "error-recovery semantics, and pricing that becomes punitive at volume. "
        "Accounts we win from Zapier are almost always ones that outgrew it "
        "rather than ones that disliked it.",
    ),
    Chunk(
        "comp-workato", "competitive_landscape_2026.pdf", 3,
        "Workato is the most frequent head-to-head and the hardest to displace, "
        "with a mature governance story and strong enterprise references. Its "
        "vulnerabilities are implementation cost and time to first value — "
        "typically a six to ten week paid onboarding — and a recipe model that "
        "practitioners describe as difficult to test.",
    ),
    Chunk(
        "comp-mulesoft", "competitive_landscape_2026.pdf", 4,
        "MuleSoft rarely appears in our deals below $100k and when it does the "
        "evaluation is usually being run by central IT rather than by the team "
        "with the problem. Its capacity-based pricing and long implementation "
        "cycles make it a poor fit for the buyers we serve, and we lose to it "
        "mainly on procurement standardisation rather than on capability.",
    ),
    Chunk(
        "comp-winrate", "competitive_landscape_2026.pdf", 4,
        "Head-to-head win rates for the year: 61% against Zapier, 38% against "
        "Workato, 44% against Tray.io, and 22% against MuleSoft. The Workato "
        "figure has improved nine points since the governance features shipped "
        "in Q1 but remains the largest single source of lost revenue in the "
        "competitive set.",
    ),
    Chunk(
        "comp-positioning", "competitive_landscape_2026.pdf", 5,
        "Positioning centres on time to first working integration, measured in "
        "hours rather than weeks, and on treating integrations as testable code "
        "rather than as configuration. This lands with technical operations "
        "buyers and lands poorly with central IT, which reads the same message "
        "as a governance risk.",
    ),
    Chunk(
        "comp-buyer-shift", "competitive_landscape_2026.pdf", 5,
        "The clearest trend in buyer behaviour is the expectation that "
        "automation is embedded in tools already owned rather than bought as a "
        "separate platform. Application vendors shipping native automation are "
        "compressing the low end of the market, which is where Zapier's volume "
        "sits and where our self-serve tier competes.",
    ),
    Chunk(
        "comp-analyst", "competitive_landscape_2026.pdf", 6,
        "Analyst coverage placed us in the challenger quadrant for the second "
        "year, with the written critique focused on partner ecosystem depth and "
        "on the absence of an on-premises deployment option. Neither is planned. "
        "The same note called our error-handling model the strongest in the "
        "evaluated set.",
    ),
    Chunk(
        "comp-openings", "competitive_landscape_2026.pdf", 6,
        "Two openings look durable. First, none of the incumbents treats "
        "environment promotion — dev to staging to production — as a first-class "
        "concept, which every practitioner we interviewed had improvised around. "
        "Second, pricing that punishes volume creates a predictable displacement "
        "moment as customers scale.",
    ),

    # ── customer_research_synthesis.pdf ──────────────────────────────────────
    Chunk(
        "res-method", "customer_research_synthesis.pdf", 1,
        "Eighteen interviews were conducted over six weeks by two researchers, "
        "recorded with consent and coded in Dovetail. Participants were "
        "recruited from accounts active for at least ninety days, with quotas "
        "set to cover all three segments and to include four accounts that had "
        "churned in the previous two quarters.",
    ),
    Chunk(
        "res-onboarding", "customer_research_synthesis.pdf", 2,
        "The most frequent complaint, raised unprompted in fourteen of eighteen "
        "interviews, was that getting initial data in required engineering help. "
        "Non-technical admins described reaching a mapping screen they could not "
        "reason about and stopping there. Several had waited more than a week "
        "for internal engineering time to finish a setup step.",
    ),
    Chunk(
        "res-abandonment", "customer_research_synthesis.pdf", 2,
        "Eleven of eighteen respondents said they had abandoned at least one "
        "workspace setup before succeeding on a later attempt. Where the "
        "abandoned attempt could be identified in product data, the median time "
        "from first step to abandonment was 26 minutes, and the last event was "
        "the import mapping screen in eight of eleven cases.",
    ),
    Chunk(
        "res-feature-requests", "customer_research_synthesis.pdf", 3,
        "Requests cluster into three themes: a way to test a change before it "
        "affects live data, visibility into why a run failed without reading raw "
        "logs, and bulk editing across many objects at once. The first was "
        "raised by twelve of eighteen and framed as a prerequisite for wider "
        "internal adoption rather than as a convenience.",
    ),
    Chunk(
        "res-nps", "customer_research_synthesis.pdf", 4,
        "The most recent survey returned an NPS of 34 from a 31% response rate. "
        "Promoters cite reliability and support responsiveness; detractors cite "
        "setup difficulty almost exclusively. The team plans to move to "
        "continuous sampling next quarter rather than a single quarterly send, "
        "which should improve both response rate and recency.",
    ),
    Chunk(
        "res-personas", "customer_research_synthesis.pdf", 4,
        "Three personas emerged. The technical operations lead owns the outcome "
        "and evaluates the product. The non-technical admin runs it day to day "
        "and is where setup fails. The security reviewer appears once, late, and "
        "can halt a deal — but never advocates for one.",
    ),
    Chunk(
        "res-workarounds", "customer_research_synthesis.pdf", 5,
        "Every participant maintained at least one spreadsheet alongside the "
        "product. The most common purposes were tracking which automations exist "
        "and who owns them, and recording what changed and when. Both are things "
        "the product holds but does not present in a form anyone found usable.",
    ),
    Chunk(
        "res-pricing-perception", "customer_research_synthesis.pdf", 5,
        "Pricing was described as fair by most participants and as unpredictable "
        "by nearly all of them. The distinction matters: the objection is not "
        "the amount but the inability to forecast next quarter's bill before "
        "committing to a new workload. Two participants said they had capped "
        "usage deliberately to keep the bill legible.",
    ),
    Chunk(
        "res-switching", "customer_research_synthesis.pdf", 6,
        "Participants who had switched from another tool described the same "
        "trigger: an incident their previous tool made difficult to diagnose, "
        "followed by a renewal within the next two quarters. Absent that pairing, "
        "inertia held even among people who described their existing tool as "
        "poor.",
    ),
    Chunk(
        "res-admin-burden", "customer_research_synthesis.pdf", 6,
        "Administrators reported spending between two and six hours a week on "
        "the product, most of it on access requests and on answering colleagues' "
        "questions about whether an automation had run. Neither is work the "
        "product intends to create, and both are largely mechanical.",
    ),

    # ── security_and_compliance.pdf ──────────────────────────────────────────
    Chunk(
        "sec-soc2", "security_and_compliance.pdf", 1,
        "The platform holds a SOC 2 Type II report covering security, "
        "availability, and confidentiality, most recently issued in March for a "
        "twelve-month observation window with no exceptions noted. ISO 27001 "
        "certification is in progress with an audit scheduled for the fourth "
        "quarter. Reports are available under NDA through the trust portal.",
    ),
    Chunk(
        "sec-pentest", "security_and_compliance.pdf", 1,
        "Penetration testing is performed twice yearly by an independent firm "
        "against production and the public API, with a summary letter published "
        "to the trust portal and the full report available under NDA. The most "
        "recent test returned two medium findings, both remediated within "
        "thirty days and retested.",
    ),
    Chunk(
        "sec-encryption", "security_and_compliance.pdf", 2,
        "Data is encrypted at rest with AES-256 and in transit with TLS 1.2 or "
        "above; TLS 1.0 and 1.1 were disabled last year. Keys are managed in the "
        "cloud provider's KMS with annual rotation, and customer-managed keys "
        "are available on the enterprise tier for the primary datastore.",
    ),
    Chunk(
        "sec-subprocessors", "security_and_compliance.pdf", 2,
        "The subprocessor list covers cloud hosting, email delivery, error "
        "monitoring, and support ticketing, and is published with the location "
        "and purpose of each. Customers subscribed to the change feed receive "
        "thirty days' notice before a new subprocessor is engaged and may object "
        "within that window.",
    ),
    Chunk(
        "sec-incident", "security_and_compliance.pdf", 3,
        "Security incidents are triaged within one hour of detection and "
        "customers materially affected are notified within 72 hours, or sooner "
        "where a regulation requires it. The response process covers "
        "containment, eradication, recovery, and a written post-incident review "
        "that is shared with affected customers.",
    ),
    Chunk(
        "sec-dpa", "security_and_compliance.pdf", 3,
        "A data processing addendum incorporating the EU standard contractual "
        "clauses and the UK addendum is executed with every customer processing "
        "personal data. Transfer impact assessments are maintained for each "
        "subprocessor outside the EEA, and the DPA is available for "
        "countersignature before contract.",
    ),
    Chunk(
        "sec-access", "security_and_compliance.pdf", 4,
        "Internal access to production follows least privilege, is granted "
        "just-in-time for a maximum of eight hours, and requires a linked ticket "
        "and second approval. All access is logged and reviewed quarterly. "
        "Standing production access is held by four staff, all in the "
        "infrastructure team.",
    ),
    Chunk(
        "sec-bcdr", "security_and_compliance.pdf", 4,
        "Backups are taken continuously with point-in-time recovery for 35 days "
        "and are replicated within the selected region. The recovery point "
        "objective is 5 minutes and the recovery time objective 4 hours. Restore "
        "drills are run quarterly and the last three met both objectives.",
    ),
    Chunk(
        "sec-vuln", "security_and_compliance.pdf", 5,
        "A public vulnerability disclosure policy provides a security contact "
        "and a safe-harbour commitment for good-faith research. Reports are "
        "acknowledged within two business days. Critical findings are remediated "
        "within seven days, high within thirty, and medium within ninety, "
        "measured from triage rather than from report.",
    ),
    Chunk(
        "sec-training", "security_and_compliance.pdf", 5,
        "All staff complete security awareness training on joining and annually "
        "thereafter, with engineers taking an additional secure development "
        "module covering the OWASP Top 10. Phishing simulations are run "
        "quarterly; the most recent reported a 4% click rate and a 61% report "
        "rate.",
    ),
]


# ── golden queries ───────────────────────────────────────────────────────────
#
# `kind` slices the report:
#   lookup      — the query and the chunk share vocabulary
#   paraphrase  — the answer is there but the wording is not; dense retrieval's job
#   exact-term  — hinges on a literal token; the lexical half's job
#   multi-chunk — a complete answer needs more than one chunk
#   near-miss   — a topically adjacent chunk exists that does NOT answer it

GOLDEN: list[Golden] = [
    # ── lookup ───────────────────────────────────────────────────────────────
    Golden("What is the current annual recurring revenue?", ("biz-arr",), ("biz-segment-mix",)),
    Golden("What was gross churn last quarter?", ("biz-churn",), ("biz-arr",), kind="near-miss"),
    Golden("How large is the total addressable market?", ("biz-tam",)),
    Golden("What is the hiring plan for next year?", ("biz-headcount",)),
    Golden("Why do we lose deals?", ("biz-loss-reasons",), ("comp-winrate",)),
    Golden("What went wrong with the Q2 launch?", ("biz-launch-retro",)),
    Golden("What is pipeline coverage going into Q4?", ("biz-pipeline",)),
    Golden("What are the rate limits on the API?", ("doc-rate-limits",)),
    Golden("How does webhook retry work?", ("doc-webhooks",)),
    Golden("Which SDKs are officially supported?", ("doc-sdks",)),
    Golden("How long are activity logs retained?", ("doc-retention",)),
    Golden("What are the file size limits for bulk import?", ("doc-import",)),
    Golden("Is the platform SOC 2 certified?", ("sec-soc2",)),
    Golden("How often is penetration testing performed?", ("sec-pentest",), ("sec-vuln",)),
    Golden("What is the incident notification timeline?", ("sec-incident",)),
    Golden("Who are the main competitors?", ("comp-set",), ("comp-winrate",)),
    Golden("What are the head-to-head win rates?", ("comp-winrate",)),
    Golden("How does our pricing compare to competitors?", ("comp-pricing",)),
    Golden("What did customers say about onboarding?", ("res-onboarding",), ("res-abandonment",)),
    Golden("What is the current NPS?", ("res-nps",)),
    Golden("What features do customers ask for most?", ("res-feature-requests",)),
    Golden("How many customer interviews were conducted and how?", ("res-method",)),

    # ── paraphrase: the answer never uses the query's words ──────────────────
    Golden(
        "How long does it take to close a big deal?",
        ("biz-sales-cycle",), ("biz-pipeline",), kind="paraphrase",
    ),
    Golden(
        "How long before we make back what we spend winning a customer?",
        ("biz-cac-payback",), kind="paraphrase",
    ),
    Golden(
        "Can I stop my data from leaving Europe?",
        ("doc-residency",), ("sec-dpa",), kind="paraphrase",
    ),
    Golden(
        "How do I keep the directory and the product in sync when someone leaves?",
        ("doc-sso",), ("sec-access",), kind="paraphrase",
    ),
    Golden(
        "Where can I try things without breaking anything real?",
        ("doc-sandbox",), ("res-feature-requests",), kind="paraphrase",
    ),
    Golden(
        "How much warning do we get before an integration breaks?",
        ("doc-versioning",), kind="paraphrase",
    ),
    Golden(
        "What happens if the whole thing goes down — how much would we lose?",
        ("sec-bcdr",), ("sec-incident",), kind="paraphrase",
    ),
    Golden(
        "Do your own staff read customer data?",
        ("sec-access",), ("sec-training",), kind="paraphrase",
    ),
    Golden(
        "Who actually decides whether to buy this?",
        ("res-personas",), kind="paraphrase",
    ),
    Golden(
        "Why do people leave the tool they already have?",
        ("res-switching",), kind="paraphrase",
    ),
    Golden(
        "Are customers happy with what they pay?",
        ("res-pricing-perception",), ("res-nps",), kind="paraphrase",
    ),
    Golden(
        "What is everyone doing in Excel that the product should be doing?",
        ("res-workarounds",), ("res-admin-burden",), kind="paraphrase",
    ),
    Golden(
        "Where are the incumbents weakest?",
        ("comp-openings",), ("comp-zapier", "comp-workato"), kind="paraphrase",
    ),
    Golden(
        "Is the market moving away from standalone tools?",
        ("comp-buyer-shift",), kind="paraphrase",
    ),
    Golden(
        "How much of the day does running this cost an administrator?",
        ("res-admin-burden",), kind="paraphrase",
    ),

    # ── exact-term: hinges on a literal token ────────────────────────────────
    Golden("What does ACM-429 mean?", ("doc-rate-limits",), ("doc-errors",), kind="exact-term"),
    Golden("What does ACM-422 indicate?", ("doc-errors",), kind="exact-term"),
    Golden("Do you support SCIM?", ("doc-sso",), kind="exact-term"),
    Golden("Is data encrypted with AES-256?", ("sec-encryption",), kind="exact-term"),
    Golden("What is the X-Acme-Signature header?", ("doc-webhooks",), kind="exact-term"),
    Golden("Do you sign a DPA with SCCs?", ("sec-dpa",), kind="exact-term"),
    Golden("Is PKCE used in the OAuth flow?", ("doc-api-auth",), kind="exact-term"),
    Golden("What is the RPO and RTO?", ("sec-bcdr",), kind="exact-term"),
    Golden("Are you in the Gartner challenger quadrant?", ("comp-analyst",), kind="exact-term"),
    Golden("Does the team use Dovetail for research?", ("res-method",), kind="exact-term"),

    # ── multi-chunk: no single chunk is a complete answer ────────────────────
    Golden(
        "What do we know about why setup fails for new customers?",
        ("res-onboarding", "res-abandonment"), ("biz-launch-retro", "doc-import"),
        kind="multi-chunk",
    ),
    Golden(
        "Summarise our competitive position against Workato.",
        ("comp-workato", "comp-winrate"), ("comp-set", "comp-positioning"),
        kind="multi-chunk",
    ),
    Golden(
        "What would a security reviewer need to see before approving us?",
        ("sec-soc2", "sec-pentest"), ("sec-encryption", "sec-dpa", "res-personas"),
        kind="multi-chunk",
    ),
    Golden(
        "How healthy is revenue growth once churn is accounted for?",
        ("biz-arr", "biz-churn"), ("biz-segment-mix",),
        kind="multi-chunk",
    ),
    Golden(
        "What authentication and authorisation options does the API offer?",
        ("doc-api-auth", "doc-sso"), ("doc-errors",),
        kind="multi-chunk",
    ),

    # ── near-miss: an adjacent chunk exists that does not answer it ──────────
    Golden(
        "How many support tickets did we handle?",
        ("biz-support-load",), ("res-admin-burden",), kind="near-miss",
    ),
    Golden(
        "What is the survey response rate?",
        ("res-nps",), ("res-method",), kind="near-miss",
    ),
    Golden(
        "What is being asked of the board this quarter?",
        ("biz-board-asks",), ("biz-headcount",), kind="near-miss",
    ),
    Golden(
        "How much revenue comes from mid-market?",
        ("biz-segment-mix",), ("biz-arr", "biz-churn"), kind="near-miss",
    ),
    Golden(
        "How quickly are critical vulnerabilities fixed?",
        ("sec-vuln",), ("sec-pentest", "sec-incident"), kind="near-miss",
    ),
    Golden(
        "What is logged for compliance purposes?",
        ("doc-audit-logs",), ("doc-retention", "sec-access"), kind="near-miss",
    ),
    Golden(
        "Who are your subprocessors and how do we hear about changes?",
        ("sec-subprocessors",), ("sec-dpa",), kind="near-miss",
    ),
    Golden(
        "Why does MuleSoft show up in our deals at all?",
        ("comp-mulesoft",), ("comp-set", "comp-winrate"), kind="near-miss",
    ),
    Golden(
        "What does security training cover for engineers?",
        ("sec-training",), kind="near-miss",
    ),
    Golden(
        "How do we describe ourselves to buyers?",
        ("comp-positioning",), ("comp-openings",), kind="near-miss",
    ),
]


# Queries this corpus genuinely cannot answer. They exist to measure the
# abstention gate against the real pipeline rather than against hand-written
# pairs: every one of these will still produce a non-empty candidate pool,
# because the lexical half matches *something* for almost any input. The
# question the harness asks is whether the re-ranker's best score stays under
# `RAG_MIN_RERANK_SCORE` so retrieval hands off to web search instead of
# formatting the least-bad chunk as evidence.
#
# They are deliberately not absurd. "What is the capital of Mongolia" is easy to
# reject; "what is our Kubernetes node count" is the realistic failure — a
# plausible internal question about a document nobody uploaded.
ADVERSARIAL: list[str] = [
    "What is our Kubernetes node count in production?",
    "How much did we spend on cloud infrastructure last month?",
    "What is the CEO's compensation package?",
    "Which law firm handles our trademark filings?",
    "What is the office lease renewal date?",
    "How many patents has the company filed?",
    "What is the current cash runway in months?",
    "Which advertising channels perform best for us?",
    "What is the mobile app's crash-free session rate?",
    "Who sits on the customer advisory board?",
]


CHUNKS_BY_ID: dict[str, Chunk] = {chunk.id: chunk for chunk in CORPUS}


def gains_for(golden: Golden) -> dict[str, int]:
    """Graded relevance for NDCG: 2 for a chunk that answers the query, 1 for a
    chunk that supports it without answering."""
    return {**{cid: 1 for cid in golden.partial}, **{cid: 2 for cid in golden.relevant}}
