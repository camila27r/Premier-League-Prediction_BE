# Import data for the 2024-2025 Premier League season into the pl_predictor database.
import os
import pandas as pd
import psycopg2
from datetime import datetime

CSV_PATH = "Data/2425.csv"      # path to the season CSV you downloaded
SEASON_LABEL = "2024-2025"          # must match format used in `seasons` table

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "pl_predictor",
    "user": "postgres",
    "password": os.environ.get("PG_PASSWORD"),   # the password you set during Postgres install
}


def main():

    # 2. READ THE CSV

    # pandas.read_csv() loads a CSV file into a "DataFrame" 
    df = pd.read_csv(CSV_PATH)

    # this prints the first 5 rows to see what pandas actually loaded
    print("Preview of loaded data:")
    print(df[["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]].head())
    print(f"\nTotal rows loaded: {len(df)}\n")

    # Converts the Date column (text) into real Python date objects, helps Postgres accepts them correctly.
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True).dt.date


    # 3. CONNECT TO POSTGRES
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("Connected to database.")

    
    # 4. INSERT THE SEASON
    # %s is a placeholder for season label
    # ON CONFLICT DO NOTHING: since season is unique, if it repeats, it will get skipped. 
    cur.execute(
        """
        INSERT INTO seasons (season_label)
        VALUES (%s)
        ON CONFLICT (season_label) DO NOTHING
        """,
        (SEASON_LABEL,),
    )
    conn.commit()

    # Fetch the season_id we just inserted (or that already existed)
    cur.execute("SELECT season_id FROM seasons WHERE season_label = %s", (SEASON_LABEL,))
    # fetchone returns first matching row as a tuple so [0] indexes for first number (3,-) -> 3
    season_id = cur.fetchone()[0]
    print(f"Season '{SEASON_LABEL}' -> season_id {season_id}")

    # 5. INSERT TEAMS
    # df[Hometeam], df[AwayTeam] are pandas series (so column of data)
    # pd.concat combines the columns into a long list and .unique removes duplicates 
    # makes sure there's 20 teams
    all_teams = pd.concat([df["HomeTeam"], df["AwayTeam"]]).unique()
    print(f"Found {len(all_teams)} unique teams.")

    # inserts all the team
    for team_name in all_teams:
        cur.execute(
            """
            INSERT INTO teams (team_name)
            VALUES (%s)
            ON CONFLICT (team_name) DO NOTHING
            """,
            (team_name,),
        )
    conn.commit()

    # Lookup dictionary: {"Arsenal": 1, "Chelsea": 2, ...}
    cur.execute("SELECT team_id, team_name FROM teams")
    # fetchall gets every row and returns a list of tuples
    # dictionary comprehension 
    team_lookup = {team_name: team_id for team_id, team_name in cur.fetchall()}

    # 6. INSERT MATCHES
    
    # df.iterrows() loops through the DataFrame one row at a time, returns (index, row)
    # row[...] pulls the column for that specific match
    inserted = 0
    for _, row in df.iterrows():
        home_id = team_lookup[row["HomeTeam"]]
        away_id = team_lookup[row["AwayTeam"]]

        # team_lookup[Arsenal], uses dictionary to return team_id 

        cur.execute(
            # populating table
            """
            INSERT INTO matches (
                season_id, match_date, home_team_id, away_team_id,
                home_goals, away_goals, full_time_result,
                ht_home_goals, ht_away_goals, half_time_result,
                referee
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                season_id,
                row["Date"],
                home_id,
                away_id,
                int(row["FTHG"]),
                int(row["FTAG"]),
                row["FTR"],
                # safety check, older season might not have half-time stats
                int(row["HTHG"]) if pd.notna(row.get("HTHG")) else None,
                int(row["HTAG"]) if pd.notna(row.get("HTAG")) else None,
                row.get("HTR"),
                row.get("Referee"),
            ),
        )
        inserted += 1

    conn.commit()
    print(f"Inserted {inserted} matches.")

    # 7. CLEAN UP

    cur.close()
    conn.close()
    print("Done. Connection closed.")


if __name__ == "__main__":
    main()