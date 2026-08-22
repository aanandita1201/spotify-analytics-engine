import pandas as pd


def transform_streaming_history(df, timezone):
    df = df.copy()

    df["local_ts"] = df["ts"].dt.tz_convert(timezone)

    df["date"] = df["local_ts"].dt.date
    df["year"] = df["local_ts"].dt.year
    df["month"] = df["local_ts"].dt.month
    df["month_name"] = df["local_ts"].dt.month_name()
    df["day_of_week"] = df["local_ts"].dt.day_name()
    df["hour"] = df["local_ts"].dt.hour
    df["minutes_played"] = df["ms_played"] / 60000

    return df