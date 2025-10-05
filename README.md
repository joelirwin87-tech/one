# Golden & Death Cross Backtester

This project provides a lightweight Flask application for uploading historical OHLCV data and
backtesting the classic golden/death cross moving average strategy with configurable trade costs.

## Getting started

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Launch the development server:

   ```bash
   flask --app app run --debug
   ```

3. Open `http://127.0.0.1:5000` in your browser. Upload a CSV file containing the following columns:

   | Column | Description |
   | ------ | ----------- |
   | `Date` | Trading date (will be parsed as a datetime) |
   | `Open` | Opening price |
   | `High` | Session high |
   | `Low` | Session low |
   | `Close` | Closing price |
   | `Volume` | Traded volume |

4. Configure the short/long moving average windows and trade cost model:

   - **Percentage**: cost applied as a percentage of trade value (e.g., `0.1` for 0.1%).
   - **Fixed amount**: cost applied per trade, denominated in the same currency as the prices.

5. Submit the form to view the trade log, strategy vs. buy-and-hold returns, and the equity curve.

## Notes

- The app assumes trades are executed on the next bar after a signal and applies transaction costs to the day the trade occurs.
- When using fixed trade costs, the strategy assumes one share per transaction and converts the cost to a percentage of the trade price.
- Always validate results against a trusted backtesting framework before using them in production.
