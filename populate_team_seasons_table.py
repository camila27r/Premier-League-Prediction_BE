"""

Populates the team_seasons table by:
1. Finding which teams played in each season (derived from `matches`)
2. Comparing each season to the one before it to detect:
   - was_promoted: team appears this season but didn't last season
   - was_relegated: team appeared last season but is gone this season
3. Inserting one row per (team, season) into team_seasons

NOTE: This only works for CONSECUTIVE seasons you've imported. If you're
missing a season in between two you have, the comparison will incorrectly
flag normal squad changes as promotion/relegation. Since your 7+ seasons
are consecutive, this should be accurate out of the box.

The very first season in your dataset has no prior season to compare
against, so every team in it is left as was_promoted = NULL (unknown)
rather than guessed at.
"""

import psycopg2
import os

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "pl_predictor",
    "user": "postgres",
    "password": os.environ.get("PG_PASSWORD"),
}


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("Connected to database.")

    
    # Get all seasons, in chronological order by using ORDER BY on the season_label (which is in YYYY-YYYY format)
    cur.execute("SELECT season_id, season_label FROM seasons ORDER BY season_label")
    seasons = cur.fetchall()  # list of (season_id, season_label) tuples
    print(f"Found {len(seasons)} seasons: {[s[1] for s in seasons]}")

   
    # For each season, get the set of team_ids that played in it
    def get_teams_for_season(season_id):
        cur.execute(
            """
            SELECT DISTINCT home_team_id FROM matches WHERE season_id = %s
            UNION
            SELECT DISTINCT away_team_id FROM matches WHERE season_id = %s
            """,
            (season_id, season_id),
            # Creates a list of team_ids that played in the given season
        )
        # Return a set of team_ids for the given season
        # cur.fetchall() returns a list of one element tuples, so use a set comprehension to extract the first element of each tuple
        return set(row[0] for row in cur.fetchall())

    # Dictionary comprehension to map each season_id to the set of team_ids that played in that season
    season_teams = {season_id: get_teams_for_season(season_id) for season_id, _ in seasons}

    # Basically, it will output something like:
    # 1: {1, 2, 3, 4, 5} teams_id for 2019-2020
    # 2: {1, 2, 3, 6, 8} teams_id for 2020-2021

    
    # Walk through seasons in order, comparing each to the previous one
    previous_teams = None
    previous_season_id = None

    for season_id, season_label in seasons:
        current_teams = season_teams[season_id]

        if previous_teams is None:
            # First season in the dataset, no prior season to compare, so we can't determine promotion/relegation
            promoted_teams = set()
            is_first_season = True
        else:
            # compares the current season's teams to previous seasons to detemine which have been promoted or relegated
            promoted_teams = current_teams - previous_teams
            relegated_teams = previous_teams - current_teams
            is_first_season = False

            # Mark relegated teams against the PREVIOUS season
            for team_id in relegated_teams:
                cur.execute(
                    """
                    UPDATE team_seasons
                    SET was_relegated = TRUE
                    WHERE team_id = %s AND season_id = %s
                    """,
                    (team_id, previous_season_id),
                )

        # Insert a row for every team in the CURRENT season
        for team_id in current_teams:
            was_promoted = team_id in promoted_teams if not is_first_season else None
            cur.execute(
                """
                INSERT INTO team_seasons (team_id, season_id, was_promoted, was_relegated)
                VALUES (%s, %s, %s, FALSE)
                ON CONFLICT (team_id, season_id) DO NOTHING
                """,
                (team_id, season_id, was_promoted),
            )

        print(
            f"{season_label}: {len(current_teams)} teams"
            + (f", {len(promoted_teams)} promoted" if not is_first_season else " (baseline season)")
        )

        previous_teams = current_teams
        previous_season_id = season_id

    conn.commit()
    cur.close()
    conn.close()
    print("\nteam_seasons populated.")


if __name__ == "__main__":
    main()