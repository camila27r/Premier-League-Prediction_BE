# Import data for all seasons.
import os
import pandas as pd
import psycopg2
from datetime import datetime


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "pl_predictor",
    "user": "postgres",
    "password": os.environ.get("PG_PASSWORD"),   # the password you set during Postgres install
}

# List of paths to the season CSV's
# season label matches format used in the 'seasons' table

SEASON_TO_IMPORT = [
    ("Data/2627.csv", "2026-2027"),
    ("Data/2526.csv", "2025-2026"),
    ("Data/2425.csv", "2024-2025"),
    ("Data/2324.csv", "2023-2024"),
    ("Data/2223.csv", "2022-2023"),
    ("Data/2122.csv", "2021-2022"),
    ("Data/2021.csv", "2020-2021"),
    ("Data/1920.csv", "2019-2020"),
    ("Data/1819.csv", "2018-2019"),
]


def main():
    # CONNECT TO POSTGRES

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("Connected to database.")

    # Loop through each season CSV and import the data
    for csv_path, season_label in SEASON_TO_IMPORT:
        print(f"Importing data for season {season_label} from {csv_path}")
        import_data(cur, conn, csv_path, season_label)

    conn.close()
    cur.close()
    print("Data import completed.")



def import_data(cur, conn, csv_path, season_label):

    # READ THE CSV
    # pandas.read_csv() loads a CSV file into a "DataFrame" 
    df = pd.read_csv(csv_path)

    # this prints the first 5 rows to see what pandas actually loaded
    print("Preview of loaded data:")
    print(df[["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]].head())
    print(f"\nTotal rows loaded: {len(df)}\n")

    # Converts the Date column (text) into real Python date objects, helps Postgres accepts them correctly.
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True).dt.date


    
    # 4. INSERT THE SEASON
    # %s is a placeholder for season label
    # ON CONFLICT DO NOTHING: since season is unique, if it repeats, it will get skipped. 
    cur.execute(
        """
        INSERT INTO seasons (season_label)
        VALUES (%s)
        ON CONFLICT (season_label) DO NOTHING
        """,
        (season_label,),
    )
    conn.commit()

    # Fetch the season_id we just inserted (or that already existed)
    cur.execute(
        """ 
        SELECT season_id 
        FROM seasons 
        WHERE season_label = %s
        """,
        (season_label,),
    )
    # fetchone returns first matching row as a tuple so [0] indexes for first number (3,-) -> 3
    season_id = cur.fetchone()[0]
    print(f"Season '{season_label}' -> season_id {season_id}")

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
            ON CONFLICT (season_id, match_date, home_team_id, away_team_id) DO NOTHING
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
    print(f"Inserted {inserted} matches for season {season_label}.")


if __name__ == "__main__":
    main()