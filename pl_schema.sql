-- ============================================================
-- Premier League Prediction Project — Database Schema
-- ============================================================
-- Designed for: football-data.co.uk CSV imports (core match data)
-- with room to layer in advanced stats (xG, shots, etc.) later
-- from FBref/Understat without restructuring.
--
-- Written in ANSI SQL / PostgreSQL-flavored syntax. Minor tweaks
-- needed for MySQL (see notes at relevant lines).
-- ============================================================

-- ---------------------------------------------------
-- 1. TEAMS
-- One row per club. Central lookup table everything
-- else references, so team names are consistent even
-- if source CSVs spell them differently across seasons
-- (e.g. "Man United" vs "Manchester United").
-- ---------------------------------------------------
CREATE TABLE teams (
    team_id       SERIAL PRIMARY KEY,        -- MySQL: INT AUTO_INCREMENT PRIMARY KEY
    team_name     VARCHAR(100) NOT NULL UNIQUE,
    short_name    VARCHAR(20)                -- optional, e.g. "MUN", useful for dashboard labels
);

-- ---------------------------------------------------
-- 2. SEASONS
-- Keeps season boundaries explicit rather than inferring
-- them from match dates. Makes "filter by season" and
-- multi-season training splits trivial later.
-- ---------------------------------------------------
CREATE TABLE seasons (
    season_id     SERIAL PRIMARY KEY,
    season_label  VARCHAR(9) NOT NULL UNIQUE, -- e.g. '2024-2025'
    start_date    DATE,
    end_date      DATE
);

-- ---------------------------------------------------
-- 3. MATCHES
-- One row per fixture. This is your core fact table —
-- almost everything else (features, predictions) joins
-- back to match_id.
-- ---------------------------------------------------
CREATE TABLE matches (
    match_id          SERIAL PRIMARY KEY,
    season_id         INT NOT NULL REFERENCES seasons(season_id),
    match_date         DATE NOT NULL,
    home_team_id       INT NOT NULL REFERENCES teams(team_id),
    away_team_id       INT NOT NULL REFERENCES teams(team_id),

    -- Full-time result
    home_goals         SMALLINT NOT NULL,
    away_goals         SMALLINT NOT NULL,
    full_time_result    CHAR(1),             -- 'H', 'D', 'A' — can be derived, but storing it
                                              -- avoids recomputing constantly in queries

    -- Half-time result (useful extra feature/signal)
    ht_home_goals       SMALLINT,
    ht_away_goals       SMALLINT,
    half_time_result     CHAR(1),

    referee            VARCHAR(100),

    CONSTRAINT chk_teams_differ CHECK (home_team_id <> away_team_id)
);

CREATE INDEX idx_matches_season ON matches(season_id);
CREATE INDEX idx_matches_home_team ON matches(home_team_id);
CREATE INDEX idx_matches_away_team ON matches(away_team_id);
CREATE INDEX idx_matches_date ON matches(match_date);

-- ---------------------------------------------------
-- 4. MATCH_STATS
-- One row PER TEAM PER MATCH (so two rows per match —
-- one for home team's stats, one for away team's stats).
-- This is where advanced stats (xG, shots, possession)
-- go once you add that layer. Kept separate from `matches`
-- so the core import (step 1) doesn't depend on having
-- this richer data yet — you can backfill it later.
-- ---------------------------------------------------
CREATE TABLE match_stats (
    match_stat_id   SERIAL PRIMARY KEY,
    match_id        INT NOT NULL REFERENCES matches(match_id),
    team_id         INT NOT NULL REFERENCES teams(team_id),
    is_home         BOOLEAN NOT NULL,         -- redundant w/ matches table but handy for fast filtering

    shots            SMALLINT,
    shots_on_target    SMALLINT,
    corners          SMALLINT,
    fouls            SMALLINT,
    yellow_cards       SMALLINT,
    red_cards        SMALLINT,
    possession_pct     DECIMAL(4,1),          -- e.g. 54.3
    xg              DECIMAL(4,2),          -- expected goals, e.g. 1.85
    xga             DECIMAL(4,2),          -- expected goals against

    UNIQUE (match_id, team_id)
);

CREATE INDEX idx_match_stats_match ON match_stats(match_id);
CREATE INDEX idx_match_stats_team ON match_stats(team_id);

-- ---------------------------------------------------
-- 5. BETTING_ODDS  (optional, add later if you want a
-- "beat the bookmakers" benchmark for your models)
-- ---------------------------------------------------
CREATE TABLE betting_odds (
    odds_id       SERIAL PRIMARY KEY,
    match_id      INT NOT NULL REFERENCES matches(match_id),
    bookmaker      VARCHAR(50) NOT NULL,
    home_odds      DECIMAL(6,2),
    draw_odds      DECIMAL(6,2),
    away_odds      DECIMAL(6,2),

    UNIQUE (match_id, bookmaker)
);

CREATE INDEX idx_betting_odds_match ON betting_odds(match_id);

-- ---------------------------------------------------
-- 6. MODEL_PREDICTIONS  (for later — once ML models exist)
-- Lets you store each model's predicted probabilities
-- per match, so Power BI can query predictions directly
-- from SQL rather than re-running Python every time.
-- ---------------------------------------------------
CREATE TABLE model_predictions (
    prediction_id     SERIAL PRIMARY KEY,
    match_id          INT NOT NULL REFERENCES matches(match_id),
    model_name         VARCHAR(50) NOT NULL,   -- e.g. 'logistic_regression', 'xgboost'
    home_win_prob       DECIMAL(5,4),
    draw_prob          DECIMAL(5,4),
    away_win_prob       DECIMAL(5,4),
    predicted_result     CHAR(1),
    actual_result       CHAR(1),               -- filled in after the match is played
    prediction_date     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (match_id, model_name)
);

CREATE INDEX idx_predictions_match ON model_predictions(match_id);
CREATE INDEX idx_predictions_model ON model_predictions(model_name);

CREATE TABLE team_seasons (
    team_id       INT NOT NULL REFERENCES teams(team_id),
    season_id     INT NOT NULL REFERENCES seasons(season_id),
    was_promoted   BOOLEAN DEFAULT FALSE,   -- promoted INTO this season
    was_relegated  BOOLEAN,                 -- relegated AT END of this season (nullable until known)

    PRIMARY KEY (team_id, season_id)
);

-- ============================================================
-- NOTES
-- ============================================================
-- - Feature-engineered fields (rolling form, points-per-game,
--   rest days, head-to-head record) are NOT stored as raw
--   columns here — those are computed in Python from this
--   base data at training time, or as SQL VIEWs. Storing raw
--   match/stat facts and deriving features on top keeps the
--   database normalized and avoids storing redundant/stale data.
-- - `full_time_result` and `half_time_result` are technically
--   derivable from the goal columns, but storing them avoids
--   recomputing a CASE expression in every query
-- - Team name mismatches across seasons/sources are the #1
--   real-world headache with this data — build your import
--   script to map/normalize names into the `teams` table rather
--   than trusting CSVs to spell teams consistently.
-- ============================================================
