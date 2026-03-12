with source as (
    select * from read_parquet('data/bronze/raw_statcast.parquet')
),

cleaned as (
    select
        -- identity
        cast("game_pk" as varchar)        as game_id,
        cast("batter" as varchar)         as batter_id,
        cast("pitcher" as varchar)        as pitcher_id,
        "player_name"                      as batter_name,
        cast("season" as integer)          as season,
        cast("game_date" as date)          as game_date,

        -- pitch info
        "pitch_type"                       as pitch_type,
        round(cast("release_speed" as double), 1)     as pitch_velocity,
        round(cast("release_spin_rate" as double), 0) as spin_rate,

        -- contact quality
        round(cast("launch_speed" as double), 1)  as exit_velocity,
        round(cast("launch_angle" as double), 1)  as launch_angle,
        round(cast("hit_distance_sc" as double), 0) as hit_distance,

        -- outcome
        "events"                           as event,
        "description"                      as pitch_result,
        "bb_type"                          as batted_ball_type,

        -- advanced
        round(cast("estimated_ba_using_speedangle" as double), 3) as xba,
        round(cast("estimated_woba_using_speedangle" as double), 3) as xwoba

    from source
    where "events" is not null
      and "launch_speed" is not null
)

select * from cleaned