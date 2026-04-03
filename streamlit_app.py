"""
Blackjack Martingale Simulator - Streamlit Web App
"""

import random
import streamlit as st
import pandas as pd
import altair as alt
from dataclasses import dataclass, field
from typing import List

# ---------------------------------------------------------------------------
# Core simulation logic (inlined so the app is self-contained)
# ---------------------------------------------------------------------------

HARD = {
    5:  {2:'H',3:'H',4:'H',5:'H',6:'H',7:'H',8:'H',9:'H',10:'H',11:'H'},
    6:  {2:'H',3:'H',4:'H',5:'H',6:'H',7:'H',8:'H',9:'H',10:'H',11:'H'},
    7:  {2:'H',3:'H',4:'H',5:'H',6:'H',7:'H',8:'H',9:'H',10:'H',11:'H'},
    8:  {2:'H',3:'H',4:'H',5:'H',6:'H',7:'H',8:'H',9:'H',10:'H',11:'H'},
    9:  {2:'H',3:'D',4:'D',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    10: {2:'D',3:'D',4:'D',5:'D',6:'D',7:'D',8:'D',9:'D',10:'H',11:'H'},
    11: {2:'D',3:'D',4:'D',5:'D',6:'D',7:'D',8:'D',9:'D',10:'D',11:'D'},
    12: {2:'H',3:'H',4:'S',5:'S',6:'S',7:'H',8:'H',9:'H',10:'H',11:'H'},
    13: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'H',8:'H',9:'H',10:'H',11:'H'},
    14: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'H',8:'H',9:'H',10:'H',11:'H'},
    15: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'H',8:'H',9:'H',10:'H',11:'H'},
    16: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'H',8:'H',9:'H',10:'H',11:'H'},
    17: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
}
SOFT = {
    13: {2:'H',3:'H',4:'H',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    14: {2:'H',3:'H',4:'H',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    15: {2:'H',3:'H',4:'D',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    16: {2:'H',3:'H',4:'D',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    17: {2:'H',3:'D',4:'D',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    18: {2:'S',3:'D',4:'D',5:'D',6:'D',7:'S',8:'S',9:'H',10:'H',11:'H'},
    19: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
    20: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
}
PAIRS = {
    2:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'H',9:'H',10:'H',11:'H'},
    3:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'H',9:'H',10:'H',11:'H'},
    4:  {2:'H',3:'H',4:'H',5:'P',6:'P',7:'H',8:'H',9:'H',10:'H',11:'H'},
    5:  {2:'D',3:'D',4:'D',5:'D',6:'D',7:'D',8:'D',9:'D',10:'H',11:'H'},
    6:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'H',8:'H',9:'H',10:'H',11:'H'},
    7:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'H',9:'H',10:'H',11:'H'},
    8:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'P',9:'P',10:'P',11:'P'},
    9:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'S',8:'P',9:'P',10:'S',11:'S'},
    10: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
    11: {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'P',9:'P',10:'P',11:'P'},
}

RANKS = [2,3,4,5,6,7,8,9,10,10,10,10,11]

@dataclass
class Shoe:
    num_decks: int = 6
    cards: List[int] = field(default_factory=list)

    def __post_init__(self):
        self.shuffle()

    def shuffle(self):
        self.cards = (RANKS * 4 * self.num_decks)[:]
        random.shuffle(self.cards)

    def deal(self) -> int:
        if len(self.cards) / (self.num_decks * 52) < 0.25:
            self.shuffle()
        return self.cards.pop()

    def deal_hand(self):
        return [self.deal(), self.deal()]

def hand_value(cards):
    raw = sum(cards)
    n_aces = cards.count(11)
    t = raw
    while t > 21 and n_aces:
        t -= 10
        n_aces -= 1
    return t, (n_aces > 0)

def is_blackjack(cards): return len(cards) == 2 and hand_value(cards)[0] == 21
def is_bust(cards):      return hand_value(cards)[0] > 21

def basic_strategy_action(player, dealer_up, can_double, can_split):
    total, soft = hand_value(player)
    if can_split and len(player) == 2 and player[0] == player[1]:
        action = PAIRS.get(player[0], {}).get(dealer_up, 'H')
        if action == 'P':
            return 'P'
    if soft and total <= 20 and total in SOFT:
        action = SOFT[total].get(dealer_up, 'H')
        return 'H' if action == 'D' and not can_double else action
    if total <= 8:  return 'H'
    if total >= 17: return 'S'
    action = HARD.get(total, {}).get(dealer_up, 'H')
    return 'H' if action == 'D' and not can_double else action

def dealer_play(hand, shoe):
    while True:
        total, soft = hand_value(hand)
        if total > 21: break
        if total > 17: break
        if total == 17 and not soft: break
        hand.append(shoe.deal())
    return hand

def fmt_cards(cards):
    return ' '.join('A' if v == 11 else str(v) for v in cards)

def play_hand(shoe, bet, bankroll):
    player = shoe.deal_hand()
    dealer = shoe.deal_hand()
    dealer_up = dealer[0]

    if is_blackjack(player):
        dealer_hand = dealer_play(dealer, shoe)
        d_total, _ = hand_value(dealer_hand)
        if is_blackjack(dealer):
            return 0, fmt_cards(player), 21, fmt_cards(dealer_hand), d_total, "PUSH (both BJ)"
        return int(bet * 1.5), fmt_cards(player), 21, fmt_cards(dealer_hand), d_total, "BLACKJACK"

    total_net = 0
    hands_played = []

    def play_one(hand, wager, is_split_ace=False):
        nonlocal total_net
        can_split  = len(hand) == 2 and hand[0] == hand[1] and wager <= bankroll + total_net
        can_double = len(hand) == 2 and wager * 2 <= bankroll + total_net
        while True:
            if is_bust(hand):
                total_net -= wager
                hands_played.append((hand[:], wager, 'BUST'))
                return
            if is_split_ace: break
            action = basic_strategy_action(hand, dealer_up, can_double, can_split)
            if action == 'S': break
            elif action == 'H':
                hand.append(shoe.deal()); can_split = False; can_double = False
            elif action == 'D':
                hand.append(shoe.deal()); wager *= 2; can_double = False; can_split = False; break
            elif action == 'P':
                c = hand[0]
                play_one([c, shoe.deal()], wager, is_split_ace=(c == 11))
                play_one([c, shoe.deal()], wager, is_split_ace=(c == 11))
                return
        if not is_bust(hand):
            hands_played.append((hand[:], wager, None))

    play_one(player, bet)
    dealer_hand = dealer_play(dealer, shoe)
    dtotal, _ = hand_value(dealer_hand)
    dealer_bust = is_bust(dealer_hand)

    results = []
    for hand, wager, preset in hands_played:
        if preset == 'BUST':
            results.append('BUST'); continue
        ptotal, _ = hand_value(hand)
        if dealer_bust or ptotal > dtotal:
            total_net += wager; results.append('WIN')
        elif ptotal == dtotal:
            results.append('PUSH')
        else:
            total_net -= wager; results.append('LOSE')

    ptotal, _ = hand_value(player)
    result_str = ' / '.join(results)
    d_display = 'BUST' if dealer_bust else str(dtotal)
    return total_net, fmt_cards(player), ptotal, fmt_cards(dealer_hand), d_display, result_str

def run_session(bankroll, base_bet, goal, max_bet):
    shoe = Shoe()
    profit = 0
    current_bet = base_bet
    rows = []

    while True:
        stop = None
        if profit >= goal:          stop = f"Goal reached! +${profit}"
        elif profit <= -bankroll:   stop = f"Bankroll busted! ${profit}"
        elif current_bet > max_bet: stop = f"Max bet ${max_bet} exceeded"
        elif current_bet > bankroll + profit: stop = f"Can't afford next bet"
        if stop:
            return rows, profit, stop

        net, p_cards, p_total, d_cards, d_total, result = play_hand(shoe, current_bet, bankroll + profit)
        profit += net
        prev_bet = current_bet

        if net > 0:
            outcome = "WIN"
            current_bet = base_bet
        elif net < 0:
            outcome = "LOSE" if "BUST" not in result else "BUST"
            current_bet *= 2
        else:
            outcome = "PUSH"

        rows.append({
            "Hand":        len(rows) + 1,
            "Bet":         f"${prev_bet}",
            "Player":      f"{p_cards} ({p_total})",
            "Dealer":      f"{d_cards} ({d_total})",
            "Result":      result,
            "Outcome":     outcome,
            "Profit":      profit,
        })

def run_multi(runs, bankroll, base_bet, goal, max_bet):
    results = []
    for _ in range(runs):
        _, profit, stop = run_session(bankroll, base_bet, goal, max_bet)
        results.append({
            "profit":   profit,
            "goal_hit": profit >= goal,
            "busted":   profit <= -bankroll,
            "stop":     stop,
        })
    return results


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Blackjack Simulator", page_icon="🃏", layout="wide")
st.title("🃏 Blackjack Martingale Simulator")
st.caption("6-deck shoe, basic strategy, Martingale bet sizing")

with st.sidebar:
    st.header("Settings")
    bankroll = st.number_input("Bankroll ($)",   min_value=100,  max_value=100000, value=5000,  step=100)
    base_bet = st.number_input("Base Bet ($)",   min_value=1,    max_value=1000,   value=50,    step=5)
    goal     = st.number_input("Profit Goal ($)", min_value=10,  max_value=10000,  value=300,   step=50)
    max_bet  = st.number_input("Max Bet ($)",    min_value=50,   max_value=50000,  value=1600,  step=50)
    st.divider()
    st.caption(f"Doubling chain: {' → '.join('$'+str(base_bet * 2**i) for i in range(6))}")

tab1, tab2 = st.tabs(["Single Session", "Multi-Session Stats"])

# ------ Tab 1: Single Session ------
with tab1:
    if st.button("Deal Session", type="primary", use_container_width=True):
        rows, profit, stop_reason = run_session(bankroll, base_bet, goal, max_bet)

        col1, col2, col3, col4 = st.columns(4)
        wins   = sum(1 for r in rows if r["Outcome"] == "WIN")
        losses = sum(1 for r in rows if r["Outcome"] in ("LOSE", "BUST"))
        pushes = sum(1 for r in rows if r["Outcome"] == "PUSH")
        col1.metric("Profit",    f"${profit:+}")
        col2.metric("Hands",     len(rows))
        col3.metric("W / L / P", f"{wins} / {losses} / {pushes}")
        col4.metric("Win Rate",  f"{wins/max(len(rows),1)*100:.1f}%")

        color = "green" if profit >= goal else ("red" if profit <= -bankroll else "orange")
        st.markdown(f"**Stop reason:** :{color}[{stop_reason}]")

        df = pd.DataFrame(rows)

        def color_row(row):
            if row["Outcome"] == "WIN":
                return ["background-color: #1a3a1a"] * len(row)
            elif row["Outcome"] in ("LOSE", "BUST"):
                return ["background-color: #3a1a1a"] * len(row)
            return ["background-color: #2a2a1a"] * len(row)

        profit_col = df["Profit"].tolist()
        df["Profit"] = df["Profit"].apply(lambda x: f"${x:+}")

        styled = df.style.apply(color_row, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Running profit chart
        chart_data = pd.DataFrame({"Hand": range(1, len(rows)+1), "Profit": profit_col})
        line = alt.Chart(chart_data).mark_line(point=True).encode(
            x=alt.X("Hand:Q", title="Hand"),
            y=alt.Y("Profit:Q", title="Profit ($)"),
            color=alt.condition(alt.datum.Profit >= 0, alt.value("#4CAF50"), alt.value("#f44336"))
        ).properties(height=250, title="Running Profit")
        st.altair_chart(line, use_container_width=True)

# ------ Tab 2: Multi-Session Stats ------
with tab2:
    runs = st.slider("Number of sessions to simulate", 100, 5000, 1000, step=100)
    if st.button("Run Simulation", type="primary", use_container_width=True):
        with st.spinner(f"Simulating {runs} sessions..."):
            results = run_multi(runs, bankroll, base_bet, goal, max_bet)

        goals_hit = sum(1 for r in results if r["goal_hit"])
        busted    = sum(1 for r in results if r["busted"])
        avg_profit = sum(r["profit"] for r in results) / runs
        profits = [r["profit"] for r in results]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Goal Hit",   f"{goals_hit/runs*100:.1f}%", f"{goals_hit}/{runs} sessions")
        col2.metric("Bust Rate",  f"{busted/runs*100:.1f}%",    f"{busted} sessions")
        col3.metric("Avg Profit", f"${avg_profit:+.0f}")
        col4.metric("Avg Loss Session", f"${sum(p for p in profits if p < 0)/max(sum(1 for p in profits if p < 0),1):.0f}")

        # Profit distribution
        dist_df = pd.DataFrame({"Profit": profits})
        hist = alt.Chart(dist_df).mark_bar().encode(
            x=alt.X("Profit:Q", bin=alt.Bin(maxbins=40), title="Session Profit ($)"),
            y=alt.Y("count()", title="Sessions"),
            color=alt.condition(alt.datum.Profit >= 0, alt.value("#4CAF50"), alt.value("#f44336"))
        ).properties(height=300, title=f"Profit Distribution ({runs} sessions)")
        st.altair_chart(hist, use_container_width=True)

        # Stop reason breakdown
        from collections import Counter
        reasons = Counter(r["stop"] for r in results)
        reason_df = pd.DataFrame(reasons.items(), columns=["Reason", "Count"]).sort_values("Count", ascending=False)
        st.subheader("Stop Reasons")
        st.dataframe(reason_df, use_container_width=True, hide_index=True)
