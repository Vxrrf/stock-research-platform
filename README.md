# مرصد الأسهم — منصّة البحث الاستثماري الشخصية

A personal **investment research system** (not a buy-signal machine) that screens
U.S. growth stocks with crisis protection, applies a **halal hard gate**, and emits
CSVs + an HTML dashboard. It never says “BUY NOW”. Every output carries its data
source, last-updated time, freshness, and a confidence rating.

Built on top of the original screener (the old `run.py` flow still
works untouched). The new platform lives in `src/` and is driven by `config.yaml`.

---

## Run it

```bash
cd mazer-system
./venv/bin/python src/main.py --watchlist     # fast: your 19-name watchlist (~1 min)
./venv/bin/python src/main.py                 # full S&P-1500 universe + watchlist (~8–10 min)
./venv/bin/python src/main.py --limit 200     # quick test on a slice of the universe
./venv/bin/python src/main.py --no-political  # skip the Congress-trades fetch
```

Outputs land in `output/`. Open `output/dashboard.html` in any browser.

---

## Data sources (FMP primary, yfinance fallback)

- **Primary: Financial Modeling Prep (FMP), the `/stable` API** (the old `/api/v3`
  endpoints are discontinued). Put your key in the **git-ignored** `config.local.yaml`
  → `data.fmp_api_key` (preferred — never commit secrets), or set the
  `FMP_API_KEY` environment variable. `config.local.yaml` overrides `config.yaml`.
- **Fallback: yfinance** (live, free). Used automatically when FMP has no key,
  is rate-limited, or can’t supply a field. No data is ever hardcoded.

> ⚠️ **FMP free tier is not enough to be the primary source.** A free key only
> returns a small whitelist of symbols (e.g. AAPL, AMD) and excludes income
> statements — so it can’t cover your watchlist/universe and can’t unlock halal
> `pass`. The platform detects this (repeated `402 … not available under your
> current subscription`), trips a **circuit breaker**, and backs off to yfinance.
> A **paid plan (Starter ~$22–29/mo)** makes FMP the real primary across all
> symbols and unlocks interest-income → halal `pass` → real `Candidate` verdicts.

### Confidence & freshness (this governs everything)
- Price data older than **48h** → freshness `STALE` → **confidence LOW**.
- Fundamentals older than the latest quarterly window → `STALE` → confidence LOW.
- Missing core data → `MISSING` → LOW. Fresh price **and** fresh fundamentals → HIGH.

---

## The halal gate is honest, not optimistic

Status is **pass / fail / unknown** and is **never guessed**:
- `fail` → action **Avoid** (“AVOID - fails Sharia screen”). Computed from
  business activity + debt/market-cap + cash/market-cap ratios (works on free data).
- `unknown` → action **Verify Halal First**. This is the *default on free data*
  because the AAOIFI **interest-income/revenue < 5%** test needs income-statement
  detail that yfinance doesn’t expose. **Add an FMP key to unlock `pass`** (and
  therefore the **Candidate** action). We would rather say “verify” than guess.
- Always confirm a name on **Zoya / Musaffa** before acting.

> So with no FMP key you’ll see names sitting at **Verify Halal First** — that’s
> correct behaviour, not a bug. CRWV, for example, correctly shows **Avoid** (its
> debt / market-cap ≈ 55%, above the AAOIFI limit).

---

## Actions (the only five — there is no “BUY NOW”)

`Candidate` · `Research More` · `Watch` · `Verify Halal First` · `Avoid`

Candidate requires halal **pass** + strong fundamentals + acceptable risk; it is
downgraded to *Research More* when data confidence is LOW.

---

## Output files (`output/`)

| File | What |
|---|---|
| `dashboard.html` | the command center — open this first |
| `ranked_stocks.csv` | every scored name, all metrics + provenance |
| `watchlist.csv` | memory: first/highest/current score, appearances, rankings |
| `new_discoveries.csv` | newly-found names this run (universe scan only) |
| `rising_scores.csv` / `fallen_angels.csv` | score momentum vs prior runs |
| `high_conviction.csv` | Candidates with ≥2 confirmation groups + strong score |
| `discovery_log.csv` | append-only audit log of every run |
| `earnings_tracker.csv` | next date, estimates, beat/miss streak, score adj |
| `insider_tracker.csv` | CEO/director buys, exec/heavy selling, confidence 0-10 |
| `news_impact.csv` | macro events (you maintain `data/news_events.yaml`) |
| `political_activity.csv` | Congress trades (weak signal only) |
| `portfolio_model.csv` | the allocation model + suggested holdings |
| `recommendation_report.md` | 13-section research write-up per top name |

---

## Configure (`config.yaml`)

Everything is there: FMP key, market-cap band ($1B–$100B), growth/EPS/upside
thresholds, debt ceiling, score weights, theme weights, news max-weight (5%),
political bonus cap (3), portfolio allocation, and data-freshness limits.

Cross-source lists you maintain: `data/external_lists.yaml`
(`propicks`, `investing_ai`, `analyst_strong_buy`, `personal_watchlist`).
Macro events you maintain: `data/news_events.yaml`.
Optional holdings for rebalancing flags: `data/holdings.csv`
(`ticker,buy_price,weight`).

---

## What is *not* live until you add keys / data

- **Halal `pass`** and the **Candidate** action — need FMP (interest income).
- **Live Congress data** — the free senate mirror is a public snapshot; FMP’s
  senate/house endpoints (with a key) give live data. Either way it’s a *weak
  signal only* and never the reason to like a name.
- **Analyst price targets / insider detail** are richer on FMP than on yfinance.

This is research, not advice. No output is a buy signal and no price is promised.
The decision and its responsibility are yours.
