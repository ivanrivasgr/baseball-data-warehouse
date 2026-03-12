with source as (
    select * from read_parquet('data/bronze/raw_pitching.parquet')
),

renamed as (
    select
        -- identity
        cast("IDfg" as varchar)       as player_id,
        "Name"                         as player_name,
        "Team"                         as team,
        cast("season" as integer)      as season,

        -- counting stats
        cast("G" as integer)           as games,
        cast("GS" as integer)          as games_started,
        round(cast("IP" as double), 1) as innings_pitched,
        cast("W" as integer)           as wins,
        cast("L" as integer)           as losses,
        cast("SV" as integer)          as saves,
        cast("SO" as integer)          as strikeouts,
        cast("BB" as integer)          as walks,
        cast("HR" as integer)          as home_runs_allowed,

        -- rate stats
        round(cast("ERA" as double), 2)  as era,
        round(cast("WHIP" as double), 2) as whip,
        round(cast("FIP" as double), 2)  as fip,
        round(cast("xFIP" as double), 2) as xfip,
        round(cast("K/9" as double), 2)  as k_per_9,
        round(cast("BB/9" as double), 2) as bb_per_9,
        round(cast("WAR" as double), 2)  as war

    from source
    where "IP" >= 20
)

select * from renamed