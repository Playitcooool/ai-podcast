# Topic selection evidence and scoring

Read this reference before automatic topic selection.

## Candidate evidence record

For every candidate, capture:

- working title, topic family, central conflict, affected audience, and episode angle;
- first observed date, latest observed date, and whether discussion is accelerating;
- at least two independent discussion signals and one factual source;
- platform or source, URL, publication date, visible engagement when available, and what the signal actually proves;
- verified facts, unresolved claims, privacy or safety concerns, and duplicate-history result.

Never invent engagement numbers. Write `unavailable` when a platform hides them.

## Chinese-internet coverage

Use `last30days` for broad discovery, then actively seek Chinese-language evidence. Prefer a mix of:

- Chinese news and primary institutional sources for facts;
- Bilibili, Zhihu, Weibo, Xiaohongshu, WeChat public articles, Chinese video platforms, or accessible hot lists for discussion signals;
- search trend tools such as Baidu Index only when directly accessible;
- Chinese-language comments or creator coverage that show more than one viewpoint.

Do not assume a global Reddit, X, TikTok, Hacker News, or YouTube trend is important in China. An imported topic needs at least one concrete Chinese-language discussion signal and a clear local analogue. If Chinese-platform evidence is unavailable, cap `中文互联网贴合度` at 5/10 and explain why.

## Scoring for broad, high-discussion reach

Score each dimension from 0–10 and calculate:

`total = youth_relevance*0.20 + emotional_resonance*0.25 + discussion_friction*0.20 + heat*0.15 + momentum*0.10 + chinese_fit*0.05 + verifiability*0.05`

- `youth_relevance`: whether the topic maps to campus, dorm, friendship, dating, group chat, gaming, short-video, AI-tool, internship, or first-job life;
- `emotional_resonance`: whether viewers recognize the awkwardness, annoyance, embarrassment, amusement, or small unfairness immediately;
- `discussion_friction`: whether ordinary viewers can take two defensible sides immediately and want to tell a personal story or argue back;
- `heat`: cross-source volume, visible engagement, and active discussion in the last 30 days;
- `momentum`: recency, acceleration, repeated resurfacing, and expected near-term continuation;
- `chinese_fit`: relevance to Chinese-language users, institutions, platforms, culture, or daily life;
- `dialogue_tension`: at least two defensible positions with meaningful human stakes;
- `verifiability`: reliable sources, manageable safety risk, and enough material for 6–12 minutes.

Favor topics that can be phrased as “你会怎么选？” or “这事到底该怪谁？”
Avoid titles that sound like conference panels, policy white papers, or abstract
concept explainers. The selected angle should contain one concrete human scene and
one comment-bait question without manufacturing outrage. Good starting patterns
include “寝室里最烦人的行为是什么？” “这种人到底算不算没边界感？” and
“你会直接说，还是选择忍到毕业？”

Round the total to two decimal places. A score is a forecast, not a fact.

## Selection gates

Reject or downgrade a candidate when:

- it relies on one viral post or an unverified allegation;
- the central question disappears without naming or attacking a specific person;
- it lacks a meaningful counter-position;
- it substantially duplicates topic history;
- its evidence is stale, circular, copied between outlets, or disconnected from Chinese-language discussion;
- safe and accurate treatment would require professional legal, medical, financial, or mental-health advice.

When the highest raw score fails a gate, record the reason and select the highest-scoring eligible candidate.

## Editorial brief table

Include a compact table with:

| Candidate | Youth relevance | Resonance | Friction | Heat | Momentum | Chinese fit | Verify | Total | Duplicate? | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|

Follow it with the evidence URLs and one paragraph explaining uncertainty in the selected forecast.
