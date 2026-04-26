# Project Gyaan
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Project Gyaan is a personal intelligence digest — an agentic pipeline that discovers, evaluates, and delivers high-quality articles straight to your inbox every week. The name comes from the Sanskrit word for "knowledge" or "wisdom".

It runs daily to collect articles, scores them for depth and originality, and sends a curated weekly email with a short AI-written briefing on what mattered most.

## How it works

**Daily pipeline** — discovers articles across multiple sources, extracts full content, evaluates each with an LLM, and stores the best ones.

**Weekly digest** — picks the top 15 articles (max 3 per topic), generates a 3-sentence week-in-review, and sends the email. Also viewable in the web UI.

**Feedback loop** — thumbs up/down on articles adjusts topic weights over time, so the digest gets better the more you use it.

## Sources

Each topic pulls from three layers in parallel:

- **Tavily search** — general web search using topic-specific queries
- **Tavily news** — articles published in the last 2 days (`topic=news`)
- **Hacker News** — topic-based search + live front page (matched to your topics)
- **RSS feeds** — curated feeds per topic (feedparser + Google News RSS)

## Topics

| Topic | Weight | Sample sources |
|---|---|---|
| Geopolitics | 1.0 | Foreign Policy, War on the Rocks, Bellingcat, CFR |
| Artificial Intelligence | 1.0 | MIT Tech Review, The Gradient, Import AI, Wired |
| History | 0.8 | JSTOR Daily, History Today, Smithsonian |
| The Guardian | 1.2 | Guardian Long Reads, Guardian World & Tech |
| Long Reads | 1.1 | Longreads, The Atlantic, The New Yorker, Vox |
| Science & Research | 0.9 | Quanta Magazine, Ars Technica, New Scientist |
| Economics & Finance | 0.9 | Noahpinion, The Economist, Marginal Revolution |

Topics, weights, and RSS feeds are all editable from the web UI.

## Scoring

Articles are scored by an LLM on three dimensions:

- **Impact** (40%) — real-world significance
- **Originality** (30%) — novel angle, non-obvious insights
- **Depth** (30%) — research rigour, evidence, detail

Combined score → `score_pct` (0–100). Only articles with `impact ≥ 6`, `depth ≥ 5`, and `worth_reading = true` make it into the digest.

## Setup

### 1. Clone and install

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/bprs68/project-gyaan.git
cd project-gyaan
uv sync
```

That's it — uv creates the virtual environment and installs all dependencies from `uv.lock`.

### 2. Create `.env`

```env
# Tavily — search and content extraction
TAVILY_API_KEY=your_tavily_api_key

# OpenRouter — LLM evaluation (uses claude-sonnet-4-6 by default)
OPENROUTER_API_KEY=your_openrouter_api_key

# Email — Gmail with App Password
SMTP_USERNAME=your_gmail_address
SMTP_PASSWORD=your_gmail_app_password
RECIPIENT_EMAIL=recipient_email_address

# Optional: LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=project-gyaan
```

### 3. Run

```bash
# Web UI + automatic daily/weekly scheduler
uv run python main.py

# Run pipeline once
uv run python main.py --daily

# Send weekly digest now
uv run python main.py --weekly

# Web UI only
uv run python main.py --web
```

The web UI runs at `http://localhost:8000` by default. The daily pipeline runs at **08:00** and the weekly digest sends every **Sunday at 20:00**.

## API keys

- **Tavily** — [app.tavily.com](https://app.tavily.com) — used for search and article extraction
- **OpenRouter** — [openrouter.ai](https://openrouter.ai) — routes to Claude for evaluation; pay-per-token
- **Gmail App Password** — Google Account → Security → 2-Step Verification → App Passwords

## Web UI

Five pages:

- **Digest** — this week's curated articles with feedback buttons and week-in-review
- **Topics** — edit topic weights, search queries, and RSS feeds
- **Library** — browse all collected articles with filters
- **Pipeline** — trigger runs manually, view run history
- **Schema** — database record counts

## Known limitations

- Paywalled articles (New Yorker, FT, Economist) are filtered out if the extractor can't get 600+ words of content
- Tavily API credits are consumed per search and extraction call
- Google News RSS returns redirect URLs that occasionally fail extraction
- LangSmith tracing requires `load_dotenv()` to run before any LangGraph imports

## Next Steps

- [x] Add Langgraph orchestration and deep agent capabilities
- [x] Develop UI to test and prototype
- [ ] Deploy to GCP for preview
- [ ] Add user login option
- [ ] Create an open source version to be used with Docker


## Preview

<video src="assets/digest-preview.mp4" controls width="100%"></video>

## License

```
MIT License

Copyright (c) 2025 bprs6869

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
