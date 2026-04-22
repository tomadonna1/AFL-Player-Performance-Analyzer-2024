import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc

# ── Data ─────────────────────────────────────────────────────────────────────
df = pd.read_csv("data/processed/stats.csv")
df.drop(["brownlow_votes", "match_attendance"], inplace=True, axis=1)

PROOF_COLS = [
    "contested_possessions", "uncontested_possessions", "clearances",
    "pressure_acts", "score_involvements", "intercepts",
    "tackles", "metres_gained", "clangers",
]

POSITIONS = ["All"] + sorted(df["position_group"].dropna().unique().tolist())

POSITION_DESCRIPTIONS = {
    "All":  "All positions",
    "MID":  "Midfielders: C, WL, WR, RR, INT, R",
    "RUC":  "Ruckmen: RK",
    "FWD":  "Forwards: FF, CHF, FPL, FPR, HFFL, HFFR",
    "DEF":  "Defenders: FB, CHB, BPL, BPR, HBFL, HBFR",
    "UTIL": "Substitute / Utility: SUB, UTIL",
}
ROUNDS = sorted(df["round_number"].unique().tolist())
ROUND_LABELS = {
    r: df.loc[df["round_number"] == r, "match_round"].iloc[0]
    for r in ROUNDS
}

PLAYER_OPTIONS = [
    {"label": n, "value": n}
    for n in sorted(df["player_name"].dropna().unique().tolist())
]

RADAR_STATS = [
    "disposals", "clearances", "tackles", "score_involvements",
    "metres_gained", "pressure_acts", "goals",
]

DARK_BG = "#0d1117"
CARD_BG = "#161b22"
BORDER  = "#30363d"
BLUE    = "#3b82f6"
ORANGE  = "#f97316"
GREEN   = "#22c55e"
AMBER   = "#f59e0b"
RED     = "#ef4444"

BADGE_COLORS = {
    "Elite":                   {"bg": GREEN,  "text": "#000"},
    "High Volume Low Impact":  {"bg": AMBER,  "text": "#000"},
    "Low Volume High Impact":  {"bg": ORANGE, "text": "#000"},
    "Balanced":                {"bg": BLUE,   "text": "#fff"},
}


def classify_players(data: pd.DataFrame) -> pd.DataFrame:
    out = data[["player_team", "player_name", "afl_fantasy_score", "rating_points", "position_group"]].copy()

    q75_fantasy = out["afl_fantasy_score"].quantile(0.75)
    q75_rating  = out["rating_points"].quantile(0.75)

    def _classify(row):
        high_fantasy = row["afl_fantasy_score"] >= q75_fantasy
        high_rating  = row["rating_points"]     >= q75_rating
        if high_fantasy and high_rating:
            return "Elite"
        elif high_fantasy and not high_rating:
            return "High Volume Low Impact"
        elif not high_fantasy and high_rating:
            return "Low Volume High Impact"
        else:
            return "Balanced"

    out["player_type"] = out.apply(_classify, axis=1)
    return out


def build_corr_table(data: pd.DataFrame) -> pd.DataFrame:
    corr_f = data[PROOF_COLS + ["afl_fantasy_score"]].corr()["afl_fantasy_score"].drop("afl_fantasy_score")
    corr_r = data[PROOF_COLS + ["rating_points"]].corr()["rating_points"].drop("rating_points")
    tbl = pd.DataFrame({"Stat": corr_f.index, "Fantasy Corr": corr_f.values.round(3), "Rating Corr": corr_r.values.round(3)})
    tbl["Driver"] = tbl.apply(
        lambda row: "Rating" if row["Rating Corr"] > row["Fantasy Corr"] else "Fantasy", axis=1
    )
    return tbl.sort_values("Rating Corr", ascending=False).reset_index(drop=True)


# ── App ───────────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="AFL Player Performance Analyzer 2024",
)
server = app.server  # for Render / gunicorn

# ── Layout ────────────────────────────────────────────────────────────────────
app.layout = dbc.Container(
    fluid=True,
    style={"backgroundColor": DARK_BG, "minHeight": "100vh", "padding": "24px"},
    children=[
        # Header
        html.Div([
            html.H2("AFL Player Performance Analyzer 2024", style={"color": "white", "margin": 0}),
            html.P("Fantasy Score vs Rating Points — Round Leaderboard", style={"color": "#8b949e", "margin": 0}),
        ], style={"marginBottom": "24px"}),

        # Controls row
        dbc.Row([
            dbc.Col([
                html.Label("Round", style={"color": "#8b949e", "fontSize": "12px"}),
                dcc.Slider(
                    id="round-slider",
                    min=min(ROUNDS), max=max(ROUNDS), step=1,
                    value=28,
                    marks={r: {"label": str(r), "style": {"color": "#8b949e", "fontSize": "10px"}}
                           for r in ROUNDS if r % 4 == 0 or r in (1, 28)},
                    # tooltip={"placement": "bottom", "always_visible": False},
                ),
            ], md=6),
            dbc.Col([
                html.Label("Position", style={"color": "#8b949e", "fontSize": "12px"}),
                dcc.RadioItems(
                    id="position-filter",
                    options=[
                        {
                            "label": html.Span(p, id=f"pos-label-{p}", style={"cursor": "help"}),
                            "value": p,
                        }
                        for p in POSITIONS
                    ],
                    value="All",
                    inline=True,
                    labelStyle={"marginRight": "12px", "color": "white", "fontSize": "13px"},
                ),
                *[
                    dbc.Tooltip(POSITION_DESCRIPTIONS.get(p, p), target=f"pos-label-{p}", placement="bottom")
                    for p in POSITIONS
                ],
            ], md=3),
            dbc.Col([
                html.Label("Sort by", style={"color": "#8b949e", "fontSize": "12px"}),
                dcc.RadioItems(
                    id="sort-metric",
                    options=[
                        {"label": "Fantasy Score", "value": "afl_fantasy_score"},
                        {"label": "Rating Points", "value": "rating_points"},
                    ],
                    value="afl_fantasy_score",
                    inline=True,
                    labelStyle={"marginRight": "12px", "color": "white", "fontSize": "13px"},
                ),
            ], md=3),
        ], style={"backgroundColor": CARD_BG, "padding": "16px", "borderRadius": "8px",
                  "border": f"1px solid {BORDER}", "marginBottom": "20px"}),

        # Round label
        html.Div(id="round-label", style={"color": "#8b949e", "fontSize": "13px", "marginBottom": "10px"}),

        # Leaderboard table
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Round Leaderboard", style={"color": "white", "margin": 0}),
                    html.Div([
                        html.Span(id="selected-player-label", style={"color": "#8b949e", "fontSize": "12px", "marginRight": "8px"}),
                        dbc.Button("Clear", id="clear-selection", size="sm", color="secondary",
                                   outline=True, style={"fontSize": "11px", "padding": "2px 8px", "display": "none"}),
                    ], style={"display": "flex", "alignItems": "center"}),
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"}),
                html.Div(id="leaderboard-table"),
            ], md=8),

            # Summary cards
            dbc.Col([
                html.H5("Round Summary", style={"color": "white", "marginBottom": "12px"}),
                html.Div(id="summary-cards"),
            ], md=4),
        ], style={"marginBottom": "24px"}),

        # Scatter + Correlation row
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Fantasy vs Rating Scatter", style={"color": "white", "margin": 0}),
                    html.Span(" ⓘ", id="scatter-info-icon",
                              style={"color": "#8b949e", "fontSize": "13px", "cursor": "help", "marginLeft": "4px"}),
                    dbc.Tooltip(
                        html.Div([
                            html.P("Players are classified using Q75 thresholds for the selected round & position filter:", style={"margin": "0 0 6px 0", "fontWeight": "600"}),
                            html.P([html.Span("● Elite", style={"color": GREEN}), " — Fantasy ≥ Q75 AND Rating ≥ Q75"], style={"margin": "2px 0"}),
                            html.P([html.Span("● High Volume Low Impact", style={"color": AMBER}), " — Fantasy ≥ Q75, Rating < Q75"], style={"margin": "2px 0"}),
                            html.P([html.Span("● Low Volume High Impact", style={"color": ORANGE}), " — Fantasy < Q75, Rating ≥ Q75"], style={"margin": "2px 0"}),
                            html.P([html.Span("● Balanced", style={"color": BLUE}), " — Fantasy < Q75 AND Rating < Q75"], style={"margin": "2px 0"}),
                        ], style={"fontSize": "12px", "padding": "4px"}),
                        target="scatter-info-icon",
                        placement="right",
                        style={"maxWidth": "360px"},
                    ),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
                html.P("Click a player to highlight them in the leaderboard",
                       style={"color": "#8b949e", "fontSize": "11px", "marginBottom": "8px"}),
                dcc.Graph(id="scatter-plot", config={"displayModeBar": False}),
            ], md=7),
            dbc.Col([
                html.H5("Stat Correlation — What Drives Each Metric?",
                        style={"color": "white", "marginBottom": "8px"}),
                html.P(
                    "Fantasy rewards uncontested ball & metres gained. "
                    "Rating rewards contested work & clearances.",
                    style={"color": "#8b949e", "fontSize": "12px", "marginBottom": "8px"},
                ),
                html.Div(id="corr-table"),
            ], md=5),
        ], style={"backgroundColor": CARD_BG, "padding": "16px", "borderRadius": "8px",
                  "border": f"1px solid {BORDER}", "marginBottom": "24px"}),

        # ── Player Profile ────────────────────────────────────────────────────
        html.Div([
            html.H4("Player Profile", style={"color": "white", "margin": 0}),
            html.P("Season-long deep-dive for any player", style={"color": "#8b949e", "fontSize": "12px", "margin": 0}),
        ], style={"marginBottom": "14px"}),

        dbc.Row([
            dbc.Col([
                html.Label("Select Player", style={"color": "#8b949e", "fontSize": "12px"}),
                dcc.Dropdown(
                    id="player-selector",
                    options=PLAYER_OPTIONS,
                    value=None,
                    placeholder="Search for a player…",
                    clearable=True,
                    style={"fontSize": "13px"},
                ),
            ], md=4),
        ], style={"backgroundColor": CARD_BG, "padding": "16px", "borderRadius": "8px",
                  "border": f"1px solid {BORDER}", "marginBottom": "16px"}),

        html.Div(id="player-profile-section", children=[
            html.P("Select a player above to view their profile.",
                   style={"color": "#8b949e", "fontSize": "13px", "textAlign": "center", "padding": "32px 0"}),
        ]),
    ],
)


# ── Callbacks ─────────────────────────────────────────────────────────────────
@app.callback(
    Output("round-label", "children"),
    Output("leaderboard-table", "children"),
    Output("summary-cards", "children"),
    Output("scatter-plot", "figure"),
    Output("corr-table", "children"),
    Output("selected-player-label", "children"),
    Output("clear-selection", "style"),
    Input("round-slider", "value"),
    Input("position-filter", "value"),
    Input("sort-metric", "value"),
    Input("scatter-plot", "clickData"),
    Input("clear-selection", "n_clicks"),
)
def update_view(round_num, position, sort_metric, click_data, _clear):
    round_label = ROUND_LABELS.get(round_num, f"Round {round_num}")

    # Filter
    slice_df = df[df["round_number"] == round_num].copy()
    if position != "All":
        slice_df = slice_df[slice_df["position_group"] == position]

    classified = classify_players(slice_df)
    classified = classified.sort_values(sort_metric, ascending=False).reset_index(drop=True)

    # Add rank columns
    classified["Fantasy Rank"] = classified["afl_fantasy_score"].rank(ascending=False, method="min").astype(int)
    classified["Rating Rank"]  = classified["rating_points"].rank(ascending=False, method="min").astype(int)
    classified["Rank Diff"]    = (classified["Fantasy Rank"] - classified["Rating Rank"]).abs()

    # ── Player selection from scatter click ──────────────────────────────────
    selected_name = None
    if ctx.triggered_id == "scatter-plot" and click_data:
        selected_name = click_data["points"][0]["text"]

    # ── Leaderboard table ────────────────────────────────────────────────────
    display_df = classified[["player_name", "position_group", "player_team", "afl_fantasy_score",
                              "rating_points", "Fantasy Rank", "Rating Rank",
                              "Rank Diff", "player_type"]].copy()
    display_df.columns = ["Player", "Position", "Team", "Fantasy", "Rating",
                          "F.Rank", "R.Rank", "Rank Diff", "Type"]

    if selected_name and selected_name in display_df["Player"].values:
        table_data = display_df[display_df["Player"] == selected_name]
    else:
        selected_name = None
        table_data = display_df

    style_data_conditional = [
        {"if": {"filter_query": "{F.Rank} <= 10"}, "backgroundColor": "#14532d33"},
        {"if": {"filter_query": "{Rank Diff} > 5"}, "backgroundColor": "#78350f33"},
        {"if": {"filter_query": "{Type} = 'Elite'", "column_id": "Type"},
         "color": GREEN, "fontWeight": "600"},
        {"if": {"filter_query": "{Type} = 'High Volume Low Impact'", "column_id": "Type"},
         "color": AMBER, "fontWeight": "600"},
        {"if": {"filter_query": "{Type} = 'Low Volume High Impact'", "column_id": "Type"},
         "color": ORANGE, "fontWeight": "600"},
        {"if": {"filter_query": "{Type} = 'Balanced'", "column_id": "Type"},
         "color": BLUE},
    ]

    table = dash_table.DataTable(
        data=table_data.to_dict("records"),
        columns=[{"name": c, "id": c} for c in display_df.columns],
        style_table={"overflowX": "auto", "borderRadius": "6px"},
        style_header={"backgroundColor": "#21262d", "color": "white",
                      "border": f"1px solid {BORDER}", "fontWeight": "600", "fontSize": "12px"},
        style_cell={"backgroundColor": CARD_BG, "color": "white",
                    "border": f"1px solid {BORDER}", "fontSize": "12px",
                    "padding": "6px 10px", "textAlign": "left"},
        style_data_conditional=style_data_conditional,
        page_size=15,
        sort_action="native",
    )

    # ── Summary cards ────────────────────────────────────────────────────────
    n_elite      = (classified["player_type"] == "Elite").sum()
    n_high_vol   = (classified["player_type"] == "High Volume Low Impact").sum()
    n_high_imp   = (classified["player_type"] == "Low Volume High Impact").sum()
    n_bal        = (classified["player_type"] == "Balanced").sum()
    med_fan  = classified["afl_fantasy_score"].median()
    med_rat  = classified["rating_points"].median()

    def card(label, value, color):
        return html.Div([
            html.P(label, style={"color": "#8b949e", "fontSize": "11px", "margin": 0}),
            html.H4(str(value), style={"color": color, "margin": 0}),
        ], style={"backgroundColor": "#21262d", "border": f"1px solid {BORDER}",
                  "borderRadius": "6px", "padding": "10px 14px", "marginBottom": "8px"})

    cards = html.Div([
        card("Median Fantasy",         round(med_fan, 1), BLUE),
        card("Median Rating",          round(med_rat, 1), ORANGE),
        card("Elite",                  n_elite, GREEN),
        card("High Volume Low Impact", n_high_vol, AMBER),
        card("Low Volume High Impact", n_high_imp, ORANGE),
        card("Balanced",               n_bal,   BLUE),
    ])

    # ── Scatter ──────────────────────────────────────────────────────────────
    color_map = {
        "Elite":                  GREEN,
        "High Volume Low Impact": AMBER,
        "Low Volume High Impact": ORANGE,
        "Balanced":               BLUE,
    }
    classified["color"] = classified["player_type"].map(color_map).fillna(BLUE)

    fig = go.Figure()
    for ptype, grp in classified.groupby("player_type", observed=True):
        fig.add_trace(go.Scatter(
            x=grp["afl_fantasy_score"], y=grp["rating_points"],
            mode="markers",
            name=str(ptype),
            marker=dict(color=color_map.get(str(ptype), BLUE), size=8, opacity=0.85),
            text=grp["player_name"],
            customdata=grp[["player_team", "Fantasy Rank", "Rating Rank"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Team: %{customdata[0]}<br>"
                "Fantasy: %{x}  (Rank #%{customdata[1]})<br>"
                "Rating: %{y}  (Rank #%{customdata[2]})<extra></extra>"
            ),
        ))

    fig.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        font=dict(color="white"),
        xaxis=dict(title="Fantasy Score", gridcolor=BORDER, zerolinecolor=BORDER),
        yaxis=dict(title="Rating Points", gridcolor=BORDER, zerolinecolor=BORDER),
        legend=dict(bgcolor=CARD_BG, bordercolor=BORDER, borderwidth=1),
        margin=dict(l=40, r=20, t=20, b=40),
        height=340,
    )

    # ── Correlation table ────────────────────────────────────────────────────
    corr_df = build_corr_table(slice_df)

    corr_style = [
        {"if": {"filter_query": "{Driver} = 'Rating'", "column_id": "Rating Corr"},
         "color": ORANGE, "fontWeight": "600"},
        {"if": {"filter_query": "{Driver} = 'Fantasy'", "column_id": "Fantasy Corr"},
         "color": BLUE, "fontWeight": "600"},
    ]

    corr_table = dash_table.DataTable(
        data=corr_df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in corr_df.columns],
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#21262d", "color": "white",
                      "border": f"1px solid {BORDER}", "fontWeight": "600", "fontSize": "12px"},
        style_cell={"backgroundColor": CARD_BG, "color": "white",
                    "border": f"1px solid {BORDER}", "fontSize": "12px",
                    "padding": "5px 10px", "textAlign": "left"},
        style_data_conditional=corr_style,
    )

    player_label = f"Filtered to: {selected_name}" if selected_name else ""
    clear_style = {"fontSize": "11px", "padding": "2px 8px"} if selected_name else {"display": "none"}

    return (
        f"Showing: {round_label}  |  {len(classified)} players",
        table,
        cards,
        fig,
        corr_table,
        player_label,
        clear_style,
    )


@app.callback(
    Output("player-profile-section", "children"),
    Input("player-selector", "value"),
)
def update_player_profile(player_name):
    if not player_name:
        return html.P("Select a player above to view their profile.",
                      style={"color": "#8b949e", "fontSize": "13px", "textAlign": "center", "padding": "32px 0"})

    pdata = df[df["player_name"] == player_name].sort_values("round_number")
    if pdata.empty:
        return html.P("No data found.", style={"color": RED})

    team        = pdata["player_team"].iloc[-1]
    pos_group   = pdata["position_group"].iloc[-1]
    games       = len(pdata)
    avg_fantasy = pdata["afl_fantasy_score"].mean()
    avg_rating  = pdata["rating_points"].mean()
    best_round  = pdata.loc[pdata["afl_fantasy_score"].idxmax(), "match_round"]
    best_score  = pdata["afl_fantasy_score"].max()
    avg_tog     = pdata["time_on_ground_percentage"].mean()
    wins        = pdata["won_match"].sum() if "won_match" in pdata.columns else 0

    def scard(label, value, color):
        return html.Div([
            html.P(label, style={"color": "#8b949e", "fontSize": "11px", "margin": 0}),
            html.H5(str(value), style={"color": color, "margin": 0}),
        ], style={"backgroundColor": "#21262d", "border": f"1px solid {BORDER}",
                  "borderRadius": "6px", "padding": "10px 14px"})

    summary_row = dbc.Row([
        dbc.Col(scard("Team",           team,                    "white"),  md=2),
        dbc.Col(scard("Position",       pos_group,               AMBER),   md=2),
        dbc.Col(scard("Games",          games,                   "white"),  md=1),
        dbc.Col(scard("Avg Fantasy",    round(avg_fantasy, 1),   BLUE),    md=2),
        dbc.Col(scard("Avg Rating",     round(avg_rating, 1),    ORANGE),  md=2),
        dbc.Col(scard("Best Round",     f"{best_round} ({int(best_score)})", GREEN), md=2),
        dbc.Col(scard("Avg TOG %",      round(avg_tog, 1),       "#8b949e"), md=1),
    ], className="g-2", style={"marginBottom": "16px"})

    # ── Line chart: Fantasy & Rating across rounds ────────────────────────────
    line_fig = go.Figure()
    line_fig.add_trace(go.Scatter(
        x=pdata["round_number"], y=pdata["afl_fantasy_score"],
        mode="lines+markers", name="Fantasy Score",
        line=dict(color=BLUE, width=2), marker=dict(size=5),
        hovertemplate="Rd %{x}: %{y}<extra>Fantasy</extra>",
    ))
    line_fig.add_trace(go.Scatter(
        x=pdata["round_number"], y=pdata["rating_points"],
        mode="lines+markers", name="Rating Points",
        line=dict(color=ORANGE, width=2), marker=dict(size=5),
        hovertemplate="Rd %{x}: %{y}<extra>Rating</extra>",
    ))
    line_fig.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        font=dict(color="white"),
        xaxis=dict(title="Round", gridcolor=BORDER, zerolinecolor=BORDER, dtick=2),
        yaxis=dict(title="Score", gridcolor=BORDER, zerolinecolor=BORDER),
        legend=dict(bgcolor=CARD_BG, bordercolor=BORDER, borderwidth=1),
        margin=dict(l=40, r=20, t=20, b=40),
        height=280,
    )

    # ── Radar: player season avg vs position group avg ────────────────────────
    pos_avg = df[df["position_group"] == pos_group][RADAR_STATS].mean()
    p_avg   = pdata[RADAR_STATS].mean()

    # Normalise to 0–1 per stat across the full dataset
    stat_max = df[RADAR_STATS].max()
    stat_max = stat_max.replace(0, 1)
    p_norm   = (p_avg   / stat_max * 100).tolist()
    g_norm   = (pos_avg / stat_max * 100).tolist()

    categories = [s.replace("_", " ").title() for s in RADAR_STATS]
    radar_fig = go.Figure()
    radar_fig.add_trace(go.Scatterpolar(
        r=p_norm + [p_norm[0]], theta=categories + [categories[0]],
        fill="toself", name=player_name,
        line=dict(color=BLUE), fillcolor="rgba(59,130,246,0.27)",
    ))
    radar_fig.add_trace(go.Scatterpolar(
        r=g_norm + [g_norm[0]], theta=categories + [categories[0]],
        fill="toself", name=f"{pos_group} avg",
        line=dict(color=ORANGE), fillcolor="rgba(249,115,22,0.2)",
    ))
    radar_fig.update_layout(
        polar=dict(
            bgcolor=CARD_BG,
            domain=dict(x=[0, 1], y=[0.15, 1]),
            radialaxis=dict(visible=True, range=[0, 100], gridcolor=BORDER, color="#8b949e"),
            angularaxis=dict(gridcolor=BORDER, color="white", rotation=90),
        ),
        paper_bgcolor=CARD_BG,
        font=dict(color="white"),
        legend=dict(
            bgcolor=CARD_BG, bordercolor=BORDER, borderwidth=1,
            orientation="h", x=0.5, xanchor="center", y=0.05,
        ),
        margin=dict(l=20, r=20, t=30, b=10),
        height=320,
    )

    # ── Per-round stats bar chart ─────────────────────────────────────────────
    GAME_STATS = ["disposals", "goals", "tackles", "clearances", "score_involvements"]
    game_bar_fig = go.Figure()
    colors = [BLUE, GREEN, ORANGE, AMBER, RED]
    for stat, color in zip(GAME_STATS, colors):
        game_bar_fig.add_trace(go.Bar(
            name=stat.replace("_", " ").title(),
            x=pdata["round_number"],
            y=pdata[stat],
            marker_color=color,
            opacity=0.85,
            hovertemplate=f"Rd %{{x}}<br>{stat.replace('_',' ').title()}: %{{y}}<extra></extra>",
        ))
    game_bar_fig.update_layout(
        barmode="stack",
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        font=dict(color="white"),
        xaxis=dict(title="Round", gridcolor=BORDER, dtick=2),
        yaxis=dict(title="Raw Stats", gridcolor=BORDER, zerolinecolor=BORDER),
        legend=dict(bgcolor=CARD_BG, bordercolor=BORDER, borderwidth=1,
                    orientation="h", x=0.5, xanchor="center", y=-0.25),
        margin=dict(l=40, r=20, t=20, b=80),
        height=300,
    )

    # ── Game log table ────────────────────────────────────────────────────────
    GAME_LOG_COLS = [
        "match_round", "opposition_team", "afl_fantasy_score", "rating_points",
        "disposals", "goals", "behinds", "tackles", "clearances",
        "score_involvements", "metres_gained", "time_on_ground_percentage",
    ]
    available_cols = [c for c in GAME_LOG_COLS if c in pdata.columns]
    game_log = pdata[["round_number"] + available_cols].copy()
    game_log = game_log.sort_values("round_number", ascending=True).drop(columns=["round_number"])
    col_labels = {
        "match_round": "Round", "opposition_team": "Opponent",
        "afl_fantasy_score": "Fantasy", "rating_points": "Rating",
        "disposals": "Disposals", "goals": "Goals", "behinds": "Behinds",
        "tackles": "Tackles", "clearances": "Clearances",
        "score_involvements": "Score Involvements", "metres_gained": "Metres",
        "time_on_ground_percentage": "TOG%",
    }
    game_log.rename(columns=col_labels, inplace=True)

    # best_fantasy = game_log["Fantasy"].max()
    # game_log_style = [
    #     {"if": {"filter_query": f"{{Fantasy}} = {best_fantasy}", "column_id": "Fantasy"},
    #      "color": GREEN, "fontWeight": "700"},
    #     {"if": {"column_id": "G", "filter_query": "{G} >= 3"}, "color": GREEN},
    #     {"if": {"column_id": "Tkl", "filter_query": "{Tkl} >= 6"}, "color": AMBER},
    # ]

    game_log_table = dash_table.DataTable(
        data=game_log.to_dict("records"),
        columns=[{"name": c, "id": c} for c in game_log.columns],
        style_table={"overflowX": "auto", "borderRadius": "6px"},
        style_header={"backgroundColor": "#21262d", "color": "white",
                      "border": f"1px solid {BORDER}", "fontWeight": "600", "fontSize": "12px"},
        style_cell={"backgroundColor": CARD_BG, "color": "white",
                    "border": f"1px solid {BORDER}", "fontSize": "12px",
                    "padding": "5px 10px", "textAlign": "center"},
        style_cell_conditional=[
            {"if": {"column_id": c}, "textAlign": "left"}
            for c in ["Round", "Opponent"]
        ],
        # style_data_conditional=game_log_style,
        sort_action="native",
        page_size=28,
    )

    # ── Bar chart: player vs position avg for selected stats ─────────────────
    bar_stats  = RADAR_STATS
    p_vals     = [round(pdata[s].mean(), 2) for s in bar_stats]
    pos_vals   = [round(df[df["position_group"] == pos_group][s].mean(), 2) for s in bar_stats]
    bar_labels = [s.replace("_", " ").title() for s in bar_stats]

    bar_fig = go.Figure()
    bar_fig.add_trace(go.Bar(
        name=player_name, x=bar_labels, y=p_vals,
        marker_color=BLUE, opacity=0.9,
    ))
    bar_fig.add_trace(go.Bar(
        name=f"{pos_group} avg", x=bar_labels, y=pos_vals,
        marker_color=ORANGE, opacity=0.7,
    ))
    bar_fig.update_layout(
        barmode="group",
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        font=dict(color="white"),
        xaxis=dict(gridcolor=BORDER, tickangle=-30),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
        legend=dict(bgcolor=CARD_BG, bordercolor=BORDER, borderwidth=1),
        margin=dict(l=40, r=20, t=20, b=60),
        height=280,
    )

    return html.Div([
        summary_row,
        dbc.Row([
            dbc.Col([
                html.H6("Fantasy & Rating — Season Arc", style={"color": "white", "marginBottom": "6px"}),
                dcc.Graph(figure=line_fig, config={"displayModeBar": False}),
            ], md=8),
            dbc.Col([
                html.H6("Stat Profile vs Position Average", style={"color": "white", "marginBottom": "6px"}),
                dcc.Graph(figure=radar_fig, config={"displayModeBar": False}),
            ], md=4),
        ], className="g-3", style={"marginBottom": "16px"}),
        dbc.Row([
            dbc.Col([
                html.H6("Season Avg vs Position Group Avg", style={"color": "white", "marginBottom": "6px"}),
                dcc.Graph(figure=bar_fig, config={"displayModeBar": False}),
            ], md=12),
        ], style={"marginBottom": "16px"}),
        dbc.Row([
            dbc.Col([
                html.H6("Per-Game Stats Breakdown", style={"color": "white", "marginBottom": "6px"}),
                html.P("Stacked bars = raw stats per round",
                       style={"color": "#8b949e", "fontSize": "11px", "marginBottom": "6px"}),
                dcc.Graph(figure=game_bar_fig, config={"displayModeBar": False}),
            ], md=12),
        ], style={"marginBottom": "16px"}),
        dbc.Row([
            dbc.Col([
                html.H6("Game Log", style={"color": "white", "marginBottom": "6px"}),
                game_log_table,
            ], md=12),
        ]),
    ], style={"backgroundColor": CARD_BG, "padding": "16px", "borderRadius": "8px",
              "border": f"1px solid {BORDER}"})


if __name__ == "__main__":
    app.run(debug=False)
