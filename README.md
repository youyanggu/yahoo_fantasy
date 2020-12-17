# Yahoo Fantasy Football
* Inspired by: https://github.com/jaredlwong/yahoo-fantasy-football

Run analysis on your Yahoo Fantasy Football league. See fun stats like which manager dropped the most valuable players, which manager had the best waiver pickups, etc.

## Installation

Create a Yahoo app here: https://developer.yahoo.com/apps/
oauth2.json file should look something like:
```
{
    "consumer_key": "<consumer key>",
    "consumer_secret": "<consumer secret>",
}
```
Also need to install yahoo_oauth: `pip install yahoo_oauth`

Then, first get the `LEAGUE_KEY` and `LEAGUE_ID` (see `main.py` for more instructions), then you can simply run `python main.py` to get the analysis.
