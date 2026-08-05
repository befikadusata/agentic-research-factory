"""Measure where the cross-encoder actually separates relevant chunks from noise.

`settings.RAG_MIN_RERANK_SCORE` decides whether retrieval answers or abstains,
and the cost of being wrong is asymmetric in a way that is easy to miss: too
high and internal documents go silently unused (the agent falls back to the web
and nobody sees a failure), too low and irrelevant excerpts come back formatted
exactly like evidence. What the model's training implies about where relevant
pairs land is a claim about the model, not about this application's documents.

So: score labelled pairs with the real model and look at the distribution.

The three labels matter separately. `relevant` is the floor the threshold must
stay below. `off_topic` is the easy case — a query about something the corpus
never mentions. `hard_negative` is the one that decides the number: same domain,
same vocabulary, genuinely does not answer the question. Those are exactly the
chunks a recall-first pool surfaces on a near-miss query, and they are what the
threshold exists to reject.

Passages are written to read like this app's corpus — uploaded market-intel
briefs, pricing pages, product docs — because a threshold calibrated on MS MARCO
web text would be calibrated for the wrong distribution.

Run it:

    uv run python -m evals.rerank_calibration

This is a calibration instrument, not a retrieval eval. It scores fixed pairs;
it does not measure whether retrieval *finds* the right chunk. `retrieval_eval.py`
does that, over a real corpus and golden queries rather than the hand-written
passages below.
"""

from dataclasses import dataclass

# (query, passage, label) — label ∈ {relevant, hard_negative, off_topic}
PAIRS: list[tuple[str, str, str]] = [
    # relevant
    (
        "What is Acme's enterprise pricing?",
        "Enterprise plans start at $2,400 per month for up to 50 seats, billed "
        "annually. Volume discounts of 15-30% apply above 200 seats, and the "
        "enterprise tier includes SSO, audit logs, and a dedicated CSM.",
        "relevant",
    ),
    (
        "How many customers churned last quarter?",
        "Q3 gross churn was 47 accounts against a starting base of 1,210, or "
        "3.9%. Net revenue retention held at 108% because expansion in the "
        "mid-market segment offset the logo loss.",
        "relevant",
    ),
    (
        "Who are the main competitors in the workflow automation space?",
        "The competitive set is dominated by Zapier at the SMB end, Workato and "
        "Tray.io in mid-market, and MuleSoft for large enterprise integration "
        "programmes. Zapier's app catalogue remains the widest moat.",
        "relevant",
    ),
    (
        "What went wrong with the Q2 product launch?",
        "The Q2 launch slipped three weeks after load testing surfaced a "
        "connection-pool exhaustion bug under concurrent imports. Post-launch, "
        "activation was 22% below forecast, which the team attributed to the "
        "onboarding flow rather than the delay itself.",
        "relevant",
    ),
    (
        "What is the company's stated security posture?",
        "The platform is SOC 2 Type II certified as of March, with penetration "
        "testing performed twice yearly by an external firm. Data is encrypted "
        "at rest with AES-256 and customer data residency is available in the "
        "EU and Australia.",
        "relevant",
    ),
    (
        "How large is the addressable market?",
        "Management sizes the total addressable market at $14.2B, derived from "
        "roughly 310,000 target companies at an average contract value of "
        "$46,000. The serviceable obtainable market over five years is put at "
        "$1.1B.",
        "relevant",
    ),
    (
        "What are the integration options for the API?",
        "The public API is REST over HTTPS with OAuth 2.0, and a GraphQL "
        "endpoint is in beta. Webhooks support 14 event types with automatic "
        "retry and exponential backoff, and official SDKs ship for Python, "
        "TypeScript, and Go.",
        "relevant",
    ),
    (
        "What is the sales cycle length for enterprise deals?",
        "Enterprise deals average 94 days from first qualified meeting to "
        "signature, extending to roughly 140 days when a security review is "
        "required. Deals with an executive sponsor identified in the first two "
        "weeks close 31% faster.",
        "relevant",
    ),
    (
        "What did the customer interviews reveal about onboarding?",
        "Across 18 customer interviews, the most frequent complaint was that "
        "initial data import required engineering help. Eleven of eighteen "
        "respondents said they abandoned at least one workspace setup before "
        "succeeding on a later attempt.",
        "relevant",
    ),
    (
        "What is the headcount plan for next year?",
        "The FY plan adds 34 roles, weighted to engineering (16) and "
        "go-to-market (12). Hiring is back-loaded into the second half, "
        "contingent on reaching $18M ARR by the end of Q2.",
        "relevant",
    ),
    (
        "How does the product handle data residency requirements?",
        "Customers may pin their workspace to the EU, US, or APAC region at "
        "provisioning time. Region cannot be changed afterwards without a "
        "migration request, and backups never leave the selected region.",
        "relevant",
    ),
    (
        "What were the reasons given for lost deals?",
        "Loss reasons recorded in the CRM cluster into three buckets: price "
        "(38%), missing SSO or compliance features (27%), and an incumbent "
        "renewal that was never genuinely contestable (21%).",
        "relevant",
    ),

    # hard negatives: same domain and vocabulary, wrong question
    (
        "What is Acme's enterprise pricing?",
        "Enterprise customers receive a dedicated customer success manager and "
        "a quarterly business review. Onboarding for the enterprise tier "
        "includes a guided migration and two training sessions for admins.",
        "hard_negative",
    ),
    (
        "How many customers churned last quarter?",
        "Customer satisfaction surveys went out to the full base in Q3, with a "
        "31% response rate. The team plans to move to a continuous NPS sampling "
        "model next quarter rather than a single quarterly send.",
        "hard_negative",
    ),
    (
        "Who are the main competitors in the workflow automation space?",
        "Workflow automation adoption is being driven by pressure to reduce "
        "manual back-office work. Buyers increasingly expect automation to be "
        "embedded in the tools they already own rather than bought separately.",
        "hard_negative",
    ),
    (
        "What went wrong with the Q2 product launch?",
        "The Q2 launch introduced three long-requested features: saved views, "
        "bulk editing, and a redesigned notification centre. Marketing ran a "
        "webinar series alongside the release.",
        "hard_negative",
    ),
    (
        "What is the company's stated security posture?",
        "The security team grew from four to seven people this year and now "
        "reports to the CTO rather than to engineering leadership. A dedicated "
        "detection engineering function is planned.",
        "hard_negative",
    ),
    (
        "How large is the addressable market?",
        "Market entry is planned in three phases, beginning with English-"
        "speaking markets before localisation into German and Japanese. Each "
        "phase is gated on reaching a support-coverage threshold.",
        "hard_negative",
    ),
    (
        "What are the integration options for the API?",
        "API request volume grew 4.1x year over year, and p99 latency held "
        "under 240ms through the peak. Rate limiting was tightened in June "
        "after a single tenant saturated a shared queue.",
        "hard_negative",
    ),
    (
        "What is the sales cycle length for enterprise deals?",
        "The enterprise sales team is organised into three pods by region, each "
        "pairing an account executive with a solutions engineer. Quota "
        "attainment across the pods ranged from 71% to 118%.",
        "hard_negative",
    ),
    (
        "What did the customer interviews reveal about onboarding?",
        "Customer interviews were conducted over six weeks by two researchers, "
        "recorded with consent, and coded in Dovetail. Participants were "
        "recruited from accounts active for at least ninety days.",
        "hard_negative",
    ),
    (
        "What is the headcount plan for next year?",
        "Employee engagement scores improved four points year over year, with "
        "the largest gain in the 'clarity of direction' dimension. Voluntary "
        "attrition was 9%, below the industry benchmark.",
        "hard_negative",
    ),
    (
        "How does the product handle data residency requirements?",
        "Data retention defaults to 24 months for activity logs, after which "
        "records are aggregated and the raw events discarded. Customers on the "
        "enterprise tier may configure a longer window.",
        "hard_negative",
    ),
    (
        "What were the reasons given for lost deals?",
        "Won deals are handed to onboarding within two business days of "
        "signature. The handover includes the discovery notes, the security "
        "questionnaire, and any commitments made during the sales cycle.",
        "hard_negative",
    ),

    # off topic: the corpus simply does not discuss this
    (
        "What is the best recipe for sourdough bread?",
        "Enterprise plans start at $2,400 per month for up to 50 seats, billed "
        "annually. Volume discounts of 15-30% apply above 200 seats.",
        "off_topic",
    ),
    (
        "Who won the 1998 World Cup?",
        "Q3 gross churn was 47 accounts against a starting base of 1,210, or "
        "3.9%. Net revenue retention held at 108%.",
        "off_topic",
    ),
    (
        "How do I treat a sprained ankle?",
        "The competitive set is dominated by Zapier at the SMB end, Workato and "
        "Tray.io in mid-market, and MuleSoft for large enterprise programmes.",
        "off_topic",
    ),
    (
        "What is the capital of Mongolia?",
        "The public API is REST over HTTPS with OAuth 2.0, and a GraphQL "
        "endpoint is in beta. Webhooks support 14 event types.",
        "off_topic",
    ),
    (
        "Explain the offside rule in football",
        "Enterprise deals average 94 days from first qualified meeting to "
        "signature, extending to roughly 140 days with a security review.",
        "off_topic",
    ),
    (
        "What year did the Berlin Wall fall?",
        "Across 18 customer interviews, the most frequent complaint was that "
        "initial data import required engineering help.",
        "off_topic",
    ),
    (
        "How does photosynthesis work?",
        "The FY plan adds 34 roles, weighted to engineering (16) and "
        "go-to-market (12). Hiring is back-loaded into the second half.",
        "off_topic",
    ),
    (
        "What is a good beginner guitar?",
        "Customers may pin their workspace to the EU, US, or APAC region at "
        "provisioning time. Region cannot be changed afterwards.",
        "off_topic",
    ),
    (
        "When should I prune apple trees?",
        "Loss reasons cluster into three buckets: price (38%), missing SSO or "
        "compliance features (27%), and uncontestable incumbent renewals (21%).",
        "off_topic",
    ),
    (
        "What causes the northern lights?",
        "The platform is SOC 2 Type II certified as of March, with penetration "
        "testing performed twice yearly by an external firm.",
        "off_topic",
    ),
]


@dataclass
class LabelStats:
    label: str
    count: int
    minimum: float
    maximum: float
    mean: float
    median: float

    def __str__(self) -> str:
        return (
            f"{self.label:<14} n={self.count:<3} "
            f"min={self.minimum:>8.3f}  median={self.median:>8.3f}  "
            f"mean={self.mean:>8.3f}  max={self.maximum:>8.3f}"
        )


def score_pairs() -> list[tuple[str, float]]:
    """Score every labelled pair with the real reranker. Returns (label, score)."""
    from tools.rag import _reranker

    model = _reranker()
    scores = model.predict([(query, passage) for query, passage, _ in PAIRS])
    return [(label, float(score)) for (_, _, label), score in zip(PAIRS, scores)]


def summarise(scored: list[tuple[str, float]]) -> dict[str, LabelStats]:
    import statistics

    by_label: dict[str, list[float]] = {}
    for label, score in scored:
        by_label.setdefault(label, []).append(score)

    return {
        label: LabelStats(
            label=label,
            count=len(values),
            minimum=min(values),
            maximum=max(values),
            mean=statistics.mean(values),
            median=statistics.median(values),
        )
        for label, values in by_label.items()
    }


def separation(scored: list[tuple[str, float]]) -> dict:
    """The numbers that actually decide the threshold.

    `margin` is the gap between the worst relevant pair and the best negative.
    Positive means some threshold separates the two sets perfectly, and the
    midpoint of that gap is the most defensible default — furthest from both
    kinds of error. Negative means no single threshold does, and the choice
    becomes an explicit trade between missed documents and admitted noise.
    """
    relevant = [s for label, s in scored if label == "relevant"]
    negatives = [s for label, s in scored if label != "relevant"]

    worst_relevant = min(relevant)
    best_negative = max(negatives)
    return {
        "worst_relevant": worst_relevant,
        "best_negative": best_negative,
        "margin": worst_relevant - best_negative,
        "midpoint": (worst_relevant + best_negative) / 2,
    }


def errors_at(scored: list[tuple[str, float]], threshold: float) -> dict:
    """How a candidate threshold misclassifies: relevant chunks it would hide,
    negatives it would admit."""
    missed = [s for label, s in scored if label == "relevant" and s < threshold]
    admitted = [(label, s) for label, s in scored if label != "relevant" and s >= threshold]
    return {
        "threshold": threshold,
        "missed_relevant": len(missed),
        "admitted_hard_negative": sum(1 for label, _ in admitted if label == "hard_negative"),
        "admitted_off_topic": sum(1 for label, _ in admitted if label == "off_topic"),
    }


def main() -> None:
    from config import settings

    scored = score_pairs()
    stats = summarise(scored)
    sep = separation(scored)

    print(f"\ncross-encoder/ms-marco-MiniLM-L-6-v2 over {len(PAIRS)} labelled pairs\n")
    for label in ("relevant", "hard_negative", "off_topic"):
        if label in stats:
            print(f"  {stats[label]}")

    print(
        f"\n  worst relevant = {sep['worst_relevant']:.3f}"
        f"   best negative = {sep['best_negative']:.3f}"
        f"   margin = {sep['margin']:.3f}"
    )
    if sep["margin"] > 0:
        print(f"  a threshold anywhere in that gap separates cleanly; midpoint = {sep['midpoint']:.3f}")
    else:
        print("  no threshold separates the sets — the default is a trade, not a cut")

    print("\n  candidate thresholds:")
    candidates = sorted({-4.0, -2.0, 0.0, 2.0, round(sep["midpoint"], 3), settings.RAG_MIN_RERANK_SCORE})
    for candidate in candidates:
        e = errors_at(scored, candidate)
        marker = "  <- configured" if candidate == settings.RAG_MIN_RERANK_SCORE else ""
        print(
            f"    {candidate:>8.3f}  missed relevant={e['missed_relevant']:<3} "
            f"admitted hard negative={e['admitted_hard_negative']:<3} "
            f"admitted off topic={e['admitted_off_topic']:<3}{marker}"
        )
    print()


if __name__ == "__main__":
    main()
