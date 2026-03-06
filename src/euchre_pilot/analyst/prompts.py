"""Prompt templates for LLM-based Euchre analysis."""

HAND_ANALYSIS_SYSTEM = """You are an expert Euchre analyst. You evaluate completed Euchre hands
and provide specific, actionable feedback on every decision made.

Your analysis should cover:
1. Bidding decisions — was ordering up / passing / calling correct given the hand?
2. Card play — was each card choice optimal? If not, what should have been played and why?
3. Key moments — which single decision had the biggest impact on the outcome?
4. Strategy principles — which fundamental principles were followed or violated?

Be concrete. Reference specific cards and specific trick numbers. Avoid vague generalities.
State what the correct play was and why, not just that a play was "suboptimal."

Euchre fundamentals for reference:
- Right bower (jack of trump) > Left bower (jack of same-color suit) > A > K > Q > 10 > 9 of trump
- Lead trump to strip opponents when you have trump strength
- Second hand low, third hand high
- Count bowers — they are the two most powerful cards
- An off-suit ace is a guaranteed trick if opponents can't trump it
- Void suits enable trumping
- 3 trump + bower is usually enough to order up
- Going alone requires near-certainty of 5 tricks
"""

HAND_ANALYSIS_TEMPLATE = """Analyze this completed Euchre hand:

Dealer: {dealer} (Seat {dealer_seat})
Trump: {trump} (called by {caller}, seat {caller_seat}{alone_note})
Turned up card: {turned_up}

Initial hands:
{initial_hands}

Bidding:
{bidding_log}

Tricks:
{tricks_log}

Result: Team {calling_team} took {calling_tricks}/5 tricks → {outcome} ({points} points for team {scoring_team})

Evaluate every decision. What was correct, what was wrong, and what was the single most impactful mistake (if any)?"""


PATTERN_ANALYSIS_TEMPLATE = """I'm analyzing {num_games} Euchre games. Here are aggregated statistics:

Win rate: {win_rate:.1%}
Euchre rate (times I was euchred): {euchre_rate:.1%}
Average tricks when calling: {avg_tricks_calling:.1f}
Going alone success rate: {alone_success_rate:.1%}

Bidding tendencies:
{bidding_stats}

Common mistakes (from individual hand analyses):
{common_mistakes}

What patterns do you see? What are the top 3 strategic adjustments that would improve results?
Focus on specific, testable changes — not generic advice."""


DECISION_REVIEW_TEMPLATE = """Should I have ordered up here?

My hand: {hand}
Turned up: {turned_up}
Trump would be: {trump_suit}
My seat: {seat} (dealer is {dealer})
Partner's seat: {partner}

With trump as {trump_suit}, my hand strength:
- Trump cards: {trump_count} ({trump_cards})
- Off-suit aces: {off_aces}
- Voids: {void_suits}

I {action}. Was this correct? What's the expected outcome of ordering up vs. passing?"""
