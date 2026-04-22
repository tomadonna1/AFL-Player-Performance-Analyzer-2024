library(fitzRoy)
library(dplyr)

# --- 1. Advanced player stats (contested possessions, clearances, hit-outs etc.)
# Fryzigg gives 81 columns including all the advanced metrics
stats_fryzigg <- fetch_player_stats(2024, source = "fryzigg")
write.csv(stats_fryzigg, "../data/raw/player_stats_fryzigg_2024.csv", row.names = FALSE)