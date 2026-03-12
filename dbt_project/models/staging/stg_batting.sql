with source as (
    select * from read_parquet('data/bronze/raw_batting.parquet')
),

renamed as (
    select
        -- identity
        cast("IDfg" as varchar)      as player_id,
        "Name"                        as player_name,
        "Team"                        as team,
        cast("season" as integer)     as season,

        -- counting stats
        cast("G" as integer)          as games,
        cast("AB" as integer)         as at_bats,
        cast("PA" as integer)         as plate_appearances,
        cast("H" as integer)          as hits,
        cast("1B" as integer)         as singles,
        cast("2B" as integer)         as doubles,
        cast("3B" as integer)         as triples,
        cast("HR" as integer)         as home_runs,
        cast("R" as integer)          as runs,
        cast("RBI" as integer)        as rbi,
        cast("SB" as integer)         as stolen_bases,
        cast("BB" as integer)         as walks,
        cast("SO" as integer)         as strikeouts,

        -- rate stats
        round(cast("AVG" as double), 3)  as avg,
        round(cast("OBP" as double), 3)  as obp,
        round(cast("SLG" as double), 3)  as slg,
        round(cast("OPS" as double), 3)  as ops,
        round(cast("wOBA" as double), 3) as woba,
        round(cast("WAR" as double), 2)  as war

    from source
    where "PA" >= 50
)

select * from renamed