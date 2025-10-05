import io
from typing import Dict

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, url_for

ALLOWED_EXTENSIONS = {"csv"}
REQUIRED_COLUMNS = {"Date", "Open", "High", "Low", "Close", "Volume"}
DEFAULT_SHORT_WINDOW = 50
DEFAULT_LONG_WINDOW = 200

app = Flask(__name__)
app.secret_key = "change-me"  # In production this should be loaded from a secure source.


def allowed_file(filename: str) -> bool:
    """Return True if the uploaded filename is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_trade_cost(cost_type: str, cost_value: str) -> Dict[str, float]:
    """Validate and normalize trade cost inputs."""
    if cost_type not in {"percent", "fixed"}:
        raise ValueError("Invalid cost type. Choose percentage or fixed cost.")
    try:
        value = float(cost_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Trade cost must be a number.") from exc
    if value < 0:
        raise ValueError("Trade cost cannot be negative.")
    return {"type": cost_type, "value": value}


def _validate_windows(short_window: str, long_window: str) -> Dict[str, int]:
    try:
        short_val = int(short_window)
        long_val = int(long_window)
    except (TypeError, ValueError) as exc:
        raise ValueError("Moving average windows must be integers.") from exc
    if short_val <= 0 or long_val <= 0:
        raise ValueError("Moving average windows must be positive numbers.")
    if short_val >= long_val:
        raise ValueError("Short window must be less than long window for a golden cross strategy.")
    return {"short": short_val, "long": long_val}


def load_dataset(file_storage) -> pd.DataFrame:
    """Read the uploaded CSV file into a DataFrame and validate columns."""
    if not allowed_file(file_storage.filename):
        raise ValueError("Only CSV files are supported.")

    content = file_storage.read()
    # Reset pointer so Flask can reuse the stream if needed
    file_storage.stream.seek(0)
    if not content:
        raise ValueError("Uploaded file is empty.")

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:  # pandas throws various exceptions
        raise ValueError("Unable to read CSV file. Ensure it is a valid comma-separated file.") from exc

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(sorted(missing))}")

    df = df.copy()
    try:
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
    except Exception as exc:
        raise ValueError("Date column must contain valid datetime values.") from exc

    df.sort_values("Date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    numeric_columns = ["Open", "High", "Low", "Close", "Volume"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
        if df[column].isna().any():
            raise ValueError(f"Column '{column}' contains non-numeric values.")

    return df


def apply_strategy(df: pd.DataFrame, short_window: int, long_window: int, cost: Dict[str, float]) -> Dict[str, object]:
    df = df.copy()
    df["Short_MA"] = df["Close"].rolling(window=short_window, min_periods=1).mean()
    df["Long_MA"] = df["Close"].rolling(window=long_window, min_periods=1).mean()

    df["Signal"] = 0
    df.loc[df["Short_MA"] > df["Long_MA"], "Signal"] = 1
    df["Position"] = df["Signal"].shift(1).fillna(0)

    df["Returns"] = df["Close"].pct_change().fillna(0)
    df["Strategy_Returns"] = df["Returns"] * df["Position"]

    trades = []
    position_changes = df["Signal"].diff().fillna(0)
    for idx, change in position_changes[position_changes != 0].items():
        signal = "Buy" if change > 0 else "Sell"
        price = df.loc[idx, "Close"]
        trade_date = df.loc[idx, "Date"]
        cost_amount = 0.0
        if cost["type"] == "percent":
            cost_amount = cost["value"] / 100
        else:
            if price == 0:
                raise ValueError("Encountered a close price of zero, cannot apply fixed trade cost.")
            cost_amount = cost["value"] / price
        df.loc[idx, "Strategy_Returns"] -= cost_amount
        trades.append({
            "date": trade_date,
            "signal": signal,
            "price": price,
            "cost_applied_pct": round(cost_amount * 100, 4),
        })

    df["Cumulative_Market_Return"] = (1 + df["Returns"]).cumprod() - 1
    df["Cumulative_Strategy_Return"] = (1 + df["Strategy_Returns"]).cumprod() - 1

    summary = {
        "total_trades": len(trades),
        "final_market_return": df.iloc[-1]["Cumulative_Market_Return"],
        "final_strategy_return": df.iloc[-1]["Cumulative_Strategy_Return"],
        "trades": trades,
        "results": df,
    }
    return summary


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded_file = request.files.get("file")
        short_window = request.form.get("short_window", str(DEFAULT_SHORT_WINDOW))
        long_window = request.form.get("long_window", str(DEFAULT_LONG_WINDOW))
        cost_type = request.form.get("cost_type", "percent")
        cost_value = request.form.get("cost_value", "0")

        if not uploaded_file or uploaded_file.filename == "":
            flash("Please upload a CSV file containing price data.", "error")
            return redirect(url_for("index"))

        try:
            df = load_dataset(uploaded_file)
            windows = _validate_windows(short_window, long_window)
            cost = parse_trade_cost(cost_type, cost_value)
            summary = apply_strategy(df, windows["short"], windows["long"], cost)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("index"))

        return render_template(
            "results.html",
            summary=summary,
            short_window=windows["short"],
            long_window=windows["long"],
            cost=cost,
        )

    return render_template(
        "index.html",
        default_short=DEFAULT_SHORT_WINDOW,
        default_long=DEFAULT_LONG_WINDOW,
    )


if __name__ == "__main__":
    app.run(debug=True)
