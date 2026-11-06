import os

import numpy as np
import pandas as pd
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "pl_predictor",
    "user": "postgres",
    "password": os.environ.get("PG_PASSWORD"),
}

OUTPUT_PATH = "data/features.csv"
FORM_WINDOW = 5  # how many past matches count as "recent form"



# 1. LOAD DATA FROM POSTGRES

def load_data():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Getting matches and their information from db
    cur.execute(
        """
        SELECT m.match_id, m.season_id, s.season_label, m.match_date,
               m.home_team_id, m.away_team_id,
               m.home_goals, m.away_goals, m.full_time_result
        FROM matches m
        JOIN seasons s ON m.season_id = s.season_id
        ORDER BY m.match_date, m.match_id
        """
    )

    # Puts data into a pandas dataframe
    cols = [c[0] for c in cur.description]
    # Although there's .fetchall() which removes the headers, we can use cur.description to get the column names and then create a DataFrame with the data and the column names.
    matches = pd.DataFrame(cur.fetchall(), columns=cols)

    # Same thing but for promotions
    cur.execute("SELECT team_id, season_id, was_promoted FROM team_seasons")
    cols = [c[0] for c in cur.description]
    team_seasons = pd.DataFrame(cur.fetchall(), columns=cols)

    cur.close()
    conn.close()

    # fixes date format and puts into a pandas datetime object
    matches["match_date"] = pd.to_datetime(matches["match_date"])
    return matches, team_seasons


# 2. Reshape from: ONE ROW PER MATCH  to  ONE ROW PER TEAM PER MATCH
# Every match becomes two rows: one from the home team's point of view, one from the away team's.
# Rolling form is easiest to compute when each team's matches sit in one
# column in date order. 

# creating home and away tables 
def to_team_rows(matches):
    home = pd.DataFrame(
        {
            "match_id": matches["match_id"],
            "season_id": matches["season_id"],
            "match_date": matches["match_date"],
            "team_id": matches["home_team_id"],
            "is_home": 1,
            "goals_for": matches["home_goals"],
            "goals_against": matches["away_goals"],
        }
    )
    away = pd.DataFrame(
        {
            "match_id": matches["match_id"],
            "season_id": matches["season_id"],
            "match_date": matches["match_date"],
            "team_id": matches["away_team_id"],
            "is_home": 0,
            "goals_for": matches["away_goals"],
            "goals_against": matches["home_goals"],
        }
    )

    # Concatening create 4 rows which 2 matches x 2 teams. Every match appears twice, once for
    # each team.
    rows = pd.concat([home, away], ignore_index=True)

    # Points earned in that match: win = 3, draw = 1, loss = 0
    rows["points"] = np.where(
        rows["goals_for"] > rows["goals_against"],
        3,
        np.where(rows["goals_for"] == rows["goals_against"], 1, 0),
    )

    # Sort so each team's matches are in chronological order
    return rows.sort_values(["team_id", "match_date", "match_id"]).reset_index(drop=True)


# 3. ROLLING FEATURES (all use shift(1) so the current match is excluded)
def add_rolling_features(rows):

    # Grouping by team so we can compute rolling features for each team separately
    by_team = rows.groupby("team_id")

    def past_mean(series):
        # shift(1) drops the current match; rolling(5) averages the 5 before it.
        # min_periods=1 lets a team with only 2 past matches still get a value.
        return series.shift(1).rolling(FORM_WINDOW, min_periods=1).mean()

    # Rolling features for the last 5 matches: form points, goals for, goals against
    rows["form_pts_5"] = by_team["points"].transform(past_mean)
    rows["gf_5"] = by_team["goals_for"].transform(past_mean)
    rows["ga_5"] = by_team["goals_against"].transform(past_mean)

    # Venue-specific form: group by team AND home/away
    rows["venue_pts_5"] = rows.groupby(["team_id", "is_home"])["points"].transform(past_mean)

    # Points per game so far this season (resets every aug.)
    rows["ppg_season"] = rows.groupby(["team_id", "season_id"])["points"].transform(
        # lambda s is a function that takes a series s and returns the expanding mean of the series, shifted by 1 to exclude the current match. This calculates the average points per game for each team in the current season, up to but not including the current match.
        lambda s: s.shift(1).expanding().mean()
    )

    # Rest days since the team's previous match. Long gaps (breaks)
    # get capped at 14 so they don't look like a huge outlier.
    rows["rest_days"] = by_team["match_date"].diff().dt.days.clip(upper=14)

    return rows


# 4. Fill Gaps

# A team's very first match in the dataset has no history, so its rolling
# values are NaN. A promoted team's early matches can also lack history.
# Fill with the league-wide average so the model gets a neutral value.
def fill_missing(rows):
    feature_cols = ["form_pts_5", "gf_5", "ga_5", "venue_pts_5", "ppg_season", "rest_days"]
    for col in feature_cols:
        rows[col] = rows[col].fillna(rows[col].mean())
    return rows


# 5. Now making it one row per match again, but with all the features we just computed. Each match has one row, with the home and away teams' features in separate columns. This is the final table that will be used for modeling.
def build_match_table(matches, rows, team_seasons):
    rows = rows.merge(team_seasons, on=["team_id", "season_id"], how="left")
    # NULL (first season, unknown) and FALSE both become 0
    rows["is_promoted"] = rows["was_promoted"].fillna(False).astype(int)

    feature_cols = [
        "form_pts_5", "gf_5", "ga_5", "venue_pts_5",
        "ppg_season", "rest_days", "is_promoted",
    ]

    # Split the rows back into home and away teams, and rename the columns so we know which is which. This will make it easier to compute differences between the two teams' features.
    home = rows[rows["is_home"] == 1][["match_id"] + feature_cols]
    home = home.rename(columns={c: f"home_{c}" for c in feature_cols})
    away = rows[rows["is_home"] == 0][["match_id"] + feature_cols]
    away = away.rename(columns={c: f"away_{c}" for c in feature_cols})

    # Building the final table.
    out = matches[["match_id", "season_label", "match_date",
                   "home_team_id", "away_team_id", "full_time_result"]].copy()
    out = out.rename(columns={"full_time_result": "result"})
    out = out.merge(home, on="match_id").merge(away, on="match_id")

    # Difference features: how much better is the home side on each measure?
    for c in ["form_pts_5", "gf_5", "ga_5", "venue_pts_5", "ppg_season", "rest_days"]:
        out[f"{c}_diff"] = out[f"home_{c}"] - out[f"away_{c}"]

    return out.sort_values(["match_date", "match_id"]).reset_index(drop=True)


def main():
    matches, team_seasons = load_data()
    print(f"Loaded {len(matches)} matches across {matches['season_label'].nunique()} seasons.")

    rows = to_team_rows(matches)
    rows = add_rolling_features(rows)
    rows = fill_missing(rows)
    features = build_match_table(matches, rows, team_seasons)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    features.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved {len(features)} rows x {len(features.columns)} columns to {OUTPUT_PATH}")
    print("\nResult distribution (share of all matches):")
    print(features["result"].value_counts(normalize=True).round(3))
    print("\nPreview:")
    print(features.head())


if __name__ == "__main__":
    main()