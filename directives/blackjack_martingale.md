# Blackjack Martingale Bot Directive

## Purpose

Automate Martingale betting strategy on 247blackjack.com using Playwright.
Stop each day once $300 profit is reached.

## Strategy: Martingale

- Start each session with a base bet (default $5)
- After a WIN: reset bet back to base bet
- After a LOSS: double the bet
- After a PUSH (tie): repeat the same bet
- Stop for the day when cumulative profit >= $300
- Stop for the day if bankroll drops below base bet (can't continue)

## Bet Sequence Example (base $5)

Win/Loss sequence: L L L W
Bets:             $5 $10 $20 $40
Result:           -5 -10 -20 +40 = net +$5 (one base unit profit)

## Risk

The Martingale strategy fails when you hit a long losing streak.
Max bet before stopping (safety limit): $640 (7 consecutive losses from $5 base).
If next required bet > $640, stop session and alert user.

## Target Site

URL: https://www.247blackjack.com/
- Free, no account needed
- Starting bankroll: $2,500 virtual
- Simple HTML UI with chip betting

## Play Strategy (Basic Strategy - simplified)

Always:
- Stand on hard 17+
- Hit on hard 8 or less
- Double on 10 or 11 (if allowed)
- Stand on soft 18+ (Ace + 7+)
- Hit on soft 17 or less (Ace + 6 or less)

Hard totals 12-16 vs dealer:
- Dealer shows 2-6: Stand
- Dealer shows 7+: Hit

Splits:
- Always split Aces and 8s
- Never split 10s or 5s

## Execution

Script: `execution/blackjack_bot.py`

```
python execution/blackjack_bot.py                    # run with defaults
python execution/blackjack_bot.py --base-bet 10      # $10 base bet
python execution/blackjack_bot.py --goal 300         # stop at $300 profit
python execution/blackjack_bot.py --headless         # run without visible browser
```

## Success Criteria

- Session ends when profit >= $300 (goal hit)
- Posts result to Discord #alerts when done
- Saves session log to .tmp/blackjack_session_YYYY-MM-DD.json

## Error Log

*Updated as issues are found.*

| Date | Error | Fix Applied |
|------|-------|-------------|
