import pandas as pd


def transform_streaming_history(df):
    df = df.copy()

    df["date"] = df["ts"].dt.date
    df["year"] = df["ts"].dt.year
    df["month"] = df["ts"].dt.month
    df["month_name"] = df["ts"].dt.month_name()
    df["day_of_week"] = df["ts"].dt.day_name()
    df["hour"] = df["ts"].dt.hour

    df["minutes_played"] = df["ms_played"] / 60000

    return df