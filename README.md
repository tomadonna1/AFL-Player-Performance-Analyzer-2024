# AFL Player Performance Analytics Dashboard 2024

A Plotly Dash web dashboard for analyzing AFL player performance in 2024, comparing AFL Fantasy scores (volume-based) vs Rating Points (impact-based).

**Live demo:** [AFL Player Performance Analytics Dashboard 2024](https://afl-player-performance-analyzer-2024.onrender.com/) 

**Data source:** [fitzRoy R package](https://github.com/jimmyday12/fitzRoy)

---

## Build steps

### Step 1 — Data collection

**Goal:** Get player statistics for the 2024 AFL season.

The `data_collection.r` script pulls three datasets from the AFL using the fitzRoy R package:

1. Player Stats
- Function: `fetch_player_stats(2024, source = "fryzigg")`
- What it gets: 81-column dataset with advanced player metrics per match — contested possessions, clearances, hit-outs, marks, tackles, disposals, etc.
- Output: `data/raw/player_stats_fryzigg_2024.csv`
- Why this source: Fryzigg provides the most comprehensive advanced stats needed for the position-adjusted scoring model in Step 3.


---

### Step 2 — Data cleaning

**Goal:** Clean the raw data and engineer features ready for the scoring model.

Script: `src/data_cleaning.py`  
Inputs: `data/raw/player_stats_fryzigg_2024.csv`, `data/raw/match_results_2024.csv`, `data/raw/ladder_2024.csv`  
Output: `data/processed/stats.csv`

#### 2.1 — Handle missing data

Three columns had significant missing values:

| Column | Missing | Action |
|---|---|---|
| `player_is_retired` | 3,932 | Fill with `False` — active players with match records are not retired |
| `supercoach_score` | 9,936 | Drop — too sparse; `afl_fantasy_score` and `rating_points` already serve as scoring benchmarks |
| `subbed` | Many | Drop — too sparse to be useful |

#### 2.2 — Drop redundant columns

Columns dropped because they duplicate or are irrelevant to per-match performance:

- `date` — duplicate of `match_date`
- `player_height_cm`, `player_weight_kg`, `guernsey_number`, `player_is_retired` — physical/administrative attributes, not relevant to match scoring

#### 2.3 — Encode categorical variables

| Column | Transformation |
|---|---|
| `player_position` | Mapped from ~18 specific positions to 5 groups: `MID`, `FWD`, `DEF`, `RUC`, `UTIL` |
| `match_winner` | Derived `won_match` binary flag: 1 if player's team won, 0 otherwise |
| `match_round` | Parsed to integer: Opening Round → 0, Rounds 1–24, Finals Week 1 → 25 through Grand Final → 28 |
| `match_weather_type` | One-hot encoded into `weather_*` binary columns |

**Position grouping rationale:** AFL positions span a wide spectrum — this mapping consolidates them into the 5 roles that the scoring model can meaningfully differentiate. `UTIL` captures substitutes and utility players who played minimal time.

#### 2.4 — Derive per-match context features

These features contextualise raw stats within match circumstances:

| Feature | Formula | Purpose |
|---|---|---|
| `is_home` | `player_team == match_home_team` | Home/away context |
| `match_closeness` | `abs(match_margin)` | How close the game was |
| `team_score` | Home or away score depending on `is_home` | Player's team's score |
| `opponent_score` | Inverse of `team_score` | Opponent's score |

---

### Step 3 — Plotly Dashboard (`app.py`)

#### 3.1 Data Setup
- Loads data/processed/stats.csv 
- Defines key constants:
  - `PROOF_COLS`: stats used for correlation analysis (contested possessions, clearances, tackles, etc.)
  - `POSITIONS`: position filter options (All, MID, RUC, FWD, DEF, UTIL)
  - `ROUNDS / ROUND_LABELS`: maps round numbers to round names (e.g. "Round 1", "Finals Week 1")
  - `RADAR_STATS`: 7 stats used for the player radar chart

#### 3.2 Help Functions
- `classify_players()`: buckets each player into one of 4 types using Q75 thresholds:
- `build_corr_table()`: computes Pearson correlations between the 9 proof stats and both Fantasy Score and Rating Points, then labels each stat as a "Fantasy driver" or "Rating driver".

#### 3.3 Layout
Three main sections:

- **Controls row**: Round slider (1–28), Position radio buttons with tooltips, Sort-by toggle (Fantasy vs Rating)
- **Leaderboard + Summary**:  Ranked table for the selected round with color-coded player types, plus 6 summary cards (medians, type counts)
- **Scatter + Correlation**: Fantasy vs Rating scatter (color-coded by type, clickable), and a correlation table showing what drives each metric
- **Player Profile**: Dropdown to select any player and view their season-long deep-dive

#### 3.4 Callbacks
`update_view()`: The main callback, fires when round/position/sort/scatter-click changes. It:
- Filters data to the selected round and position
- Classifies players and builds the leaderboard table
- Handles scatter click → highlights that player in the table
- Builds the scatter plot grouped by player type
- Builds the correlation table

`update_player_profile()`: Fires when a player is selected from the dropdown. It renders:
- Summary cards (team, position, games, avg Fantasy/Rating, best round, TOG%)
- Line chart: Fantasy & Rating scores across all rounds
- Radar chart: player season avg vs position group avg (normalized 0–100)
- Bar chart: season avg vs position group avg for the 7 radar stats
- Stacked bar chart: per-round breakdown of disposals, goals, tackles, clearances, score involvements
- Game log table: full stat line for every game played

---




