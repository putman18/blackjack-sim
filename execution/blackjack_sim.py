"""
blackjack_sim.py - Pure Python blackjack simulation (no browser)

Tests Martingale strategy with correct game rules and basic strategy.

Usage:
    py blackjack/execution/blackjack_sim.py
    py blackjack/execution/blackjack_sim.py --hands 200
    py blackjack/execution/blackjack_sim.py --bankroll 2000 --base-bet 50 --goal 300
    py blackjack/execution/blackjack_sim.py --runs 100   # run 100 sessions, show stats
"""

import argparse
import random
from dataclasses import dataclass, field
from typing import List

# ---------------------------------------------------------------------------
# Basic strategy tables
# Key: (player_total_or_pair, dealer_upcard)  Value: 'H'it, 'S'tand, 'D'ouble, 'P'split
# Dealer upcard: 2-10, A=11
# ---------------------------------------------------------------------------

# Hard totals (non-pair, non-soft)
HARD = {
    # total: {dealer_up: action}
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

# Soft totals (one ace counted as 11)
SOFT = {
    # Soft 13 = A+2, soft 21 = blackjack (already handled)
    13: {2:'H',3:'H',4:'H',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    14: {2:'H',3:'H',4:'H',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    15: {2:'H',3:'H',4:'D',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    16: {2:'H',3:'H',4:'D',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    17: {2:'H',3:'D',4:'D',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
    18: {2:'S',3:'D',4:'D',5:'D',6:'D',7:'S',8:'S',9:'H',10:'H',11:'H'},
    19: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
    20: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
}

# Pair splitting
PAIRS = {
    # pair_card_value: {dealer_up: 'P' or fall back to hard}
    2:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'H',9:'H',10:'H',11:'H'},
    3:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'H',9:'H',10:'H',11:'H'},
    4:  {2:'H',3:'H',4:'H',5:'P',6:'P',7:'H',8:'H',9:'H',10:'H',11:'H'},
    5:  {2:'D',3:'D',4:'D',5:'D',6:'D',7:'D',8:'D',9:'D',10:'H',11:'H'},  # never split 5s
    6:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'H',8:'H',9:'H',10:'H',11:'H'},
    7:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'H',9:'H',10:'H',11:'H'},
    8:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'P',9:'P',10:'P',11:'P'},  # always split 8s
    9:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'S',8:'P',9:'P',10:'S',11:'S'},
    10: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},  # never split 10s
    11: {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'P',9:'P',10:'P',11:'P'},  # always split Aces
}


# ---------------------------------------------------------------------------
# Card / Shoe
# ---------------------------------------------------------------------------

RANKS = [2,3,4,5,6,7,8,9,10,10,10,10,11]  # 10=T/J/Q/K, 11=Ace

def build_shoe(num_decks: int = 6) -> List[int]:
    deck = RANKS * 4
    return deck * num_decks

@dataclass
class Shoe:
    num_decks: int = 6
    cards: List[int] = field(default_factory=list)
    reshuffle_threshold: float = 0.25

    def __post_init__(self):
        self.shuffle()

    def shuffle(self):
        self.cards = build_shoe(self.num_decks)
        random.shuffle(self.cards)

    def deal(self) -> int:
        if len(self.cards) / (self.num_decks * 52) < self.reshuffle_threshold:
            self.shuffle()
        return self.cards.pop()

    def deal_hand(self) -> List[int]:
        return [self.deal(), self.deal()]


# ---------------------------------------------------------------------------
# Hand evaluation
# ---------------------------------------------------------------------------

def hand_value(cards: List[int]) -> tuple:
    """Returns (total, is_soft). Aces reduce from 11 to 1 as needed."""
    total = sum(cards)
    aces = cards.count(11)
    soft = False
    while total > 21 and aces:
        total -= 10
        aces -= 1
    if 11 in cards and total <= 21 and total - sum(c for c in cards if c != 11) >= 0:
        # Check if an ace is still counted as 11
        hard_total = sum(1 if c == 11 else c for c in cards)
        soft = (total - hard_total) == 10 * cards.count(11) - (cards.count(11) - aces) * 10
        # Simpler: soft if total == hard_sum + 10 (one ace still as 11)
    # Recalculate softness cleanly
    raw = sum(cards)
    n_aces = cards.count(11)
    t = raw
    while t > 21 and n_aces:
        t -= 10
        n_aces -= 1
    is_soft = (n_aces > 0)  # at least one ace still counted as 11
    return t, is_soft

def is_blackjack(cards: List[int]) -> bool:
    return len(cards) == 2 and hand_value(cards)[0] == 21

def is_bust(cards: List[int]) -> bool:
    return hand_value(cards)[0] > 21


# ---------------------------------------------------------------------------
# Basic strategy decision
# ---------------------------------------------------------------------------

def basic_strategy_action(player: List[int], dealer_up: int, can_double: bool, can_split: bool) -> str:
    """Returns 'H', 'S', 'D', 'P'."""
    total, soft = hand_value(player)

    # Pair check
    if can_split and len(player) == 2 and player[0] == player[1]:
        pair_val = player[0]  # 11 = Ace pair
        action = PAIRS.get(pair_val, {}).get(dealer_up, 'H')
        if action == 'P':
            return 'P'
        # Fall through to hard/soft logic

    # Soft hand
    if soft and total <= 20 and total in SOFT:
        action = SOFT[total].get(dealer_up, 'H')
        if action == 'D' and not can_double:
            return 'H'
        return action

    # Hard hand
    if total <= 8:
        return 'H'
    if total >= 17:
        return 'S'
    action = HARD.get(total, {}).get(dealer_up, 'H')
    if action == 'D' and not can_double:
        return 'H'
    return action


# ---------------------------------------------------------------------------
# Dealer play
# ---------------------------------------------------------------------------

def dealer_play(hand: List[int], shoe: Shoe) -> List[int]:
    """Dealer hits until hard 17+ or soft 18+."""
    while True:
        total, soft = hand_value(hand)
        if total > 21:
            break
        if total > 17:
            break
        if total == 17 and not soft:
            break
        hand.append(shoe.deal())
    return hand


# ---------------------------------------------------------------------------
# Play one hand (supports splits)
# ---------------------------------------------------------------------------

def fmt_cards(cards: List[int]) -> str:
    """Format card list for display: 11->A, others as number."""
    def c(v):
        return 'A' if v == 11 else str(v)
    return ' '.join(c(v) for v in cards)

def play_hand(shoe: Shoe, bet: int, bankroll: int) -> tuple:
    """
    Returns (net_result, hand_description).
    Description shows cards dealt and result for player and dealer.
    """
    player = shoe.deal_hand()
    dealer = shoe.deal_hand()
    dealer_up = dealer[0]

    # Natural blackjack check
    if is_blackjack(player):
        dealer_hand = dealer_play(dealer, shoe)
        d_str = f"[{fmt_cards(dealer_hand)}]={hand_value(dealer_hand)[0]}"
        if is_blackjack(dealer):
            return 0, f"Player [{fmt_cards(player)}]=BJ  Dealer {d_str} -> PUSH (both BJ)"
        return int(bet * 1.5), f"Player [{fmt_cards(player)}]=BJ  Dealer {d_str} -> BLACKJACK"

    total_net = 0
    hands_played = []

    def play_one(hand, wager, is_split_ace=False):
        nonlocal total_net
        can_split = (len(hand) == 2 and hand[0] == hand[1] and
                     wager <= bankroll + total_net)
        can_double = (len(hand) == 2 and wager * 2 <= bankroll + total_net)

        while True:
            if is_bust(hand):
                total_net -= wager
                hands_played.append((hand[:], wager, 'BUST'))
                return
            if is_split_ace:
                break

            action = basic_strategy_action(hand, dealer_up, can_double, can_split)

            if action == 'S':
                break
            elif action == 'H':
                hand.append(shoe.deal())
                can_split = False
                can_double = False
            elif action == 'D':
                hand.append(shoe.deal())
                wager *= 2
                can_double = False
                can_split = False
                break
            elif action == 'P':
                c = hand[0]
                h1 = [c, shoe.deal()]
                h2 = [c, shoe.deal()]
                is_ace = (c == 11)
                play_one(h1, wager, is_split_ace=is_ace)
                play_one(h2, wager, is_split_ace=is_ace)
                return

        if not is_bust(hand):
            hands_played.append((hand[:], wager, None))

    play_one(player, bet)

    # Dealer plays (even if all busted, show their hand)
    dealer_hand = dealer_play(dealer, shoe)
    dtotal, _ = hand_value(dealer_hand)
    dealer_bust = is_bust(dealer_hand)
    d_str = f"[{fmt_cards(dealer_hand)}]={'BUST' if dealer_bust else dtotal}"

    results = []
    for hand, wager, preset in hands_played:
        if preset == 'BUST':
            results.append(f"[{fmt_cards(hand)}]=BUST")
            continue
        ptotal, _ = hand_value(hand)
        if dealer_bust or ptotal > dtotal:
            total_net += wager
            results.append(f"[{fmt_cards(hand)}]={ptotal} WIN")
        elif ptotal == dtotal:
            results.append(f"[{fmt_cards(hand)}]={ptotal} PUSH")
        else:
            total_net -= wager
            results.append(f"[{fmt_cards(hand)}]={ptotal} LOSE")

    player_str = '  |  '.join(results)
    desc = f"Player {player_str}  Dealer {d_str}"
    return total_net, desc


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def run_session(bankroll: int, base_bet: int, goal: int, max_bet: int,
                verbose: bool = True) -> dict:
    shoe = Shoe(num_decks=6)
    profit = 0
    current_bet = base_bet
    hands = 0
    wins = losses = pushes = 0

    if verbose:
        print(f"\nBankroll: ${bankroll} | Base bet: ${base_bet} | Goal: +${goal} | Max bet: ${max_bet}")
        print("-" * 90)

    while True:
        if profit >= goal:
            if verbose:
                print(f"\nGoal reached! +${profit}")
            break
        if profit <= -bankroll:
            if verbose:
                print(f"\nBankroll busted! {profit}")
            break
        if current_bet > max_bet:
            if verbose:
                print(f"\nMax bet ${max_bet} exceeded. Stopping. Profit: ${profit:+}")
            break
        if current_bet > bankroll + profit:
            if verbose:
                print(f"\nCan't afford next bet. Stopping. Profit: ${profit:+}")
            break

        hands += 1
        net, desc = play_hand(shoe, current_bet, bankroll + profit)

        if net > 0:
            wins += 1
            profit += net
            prev_bet = current_bet
            current_bet = base_bet
            outcome = "WIN"
        elif net < 0:
            losses += 1
            profit += net
            prev_bet = current_bet
            current_bet = current_bet * 2
            outcome = "LOSE"
        else:
            pushes += 1
            outcome = "PUSH"
            prev_bet = current_bet

        if verbose:
            print(f"Hand {hands:3} | Bet: ${prev_bet:5} | {desc} | Profit: ${profit:+}")

    win_rate = wins / max(hands, 1) * 100
    if verbose:
        print("-" * 90)
        print(f"Hands: {hands} | {wins}W/{losses}L/{pushes}P | Win rate: {win_rate:.1f}% | Profit: ${profit:+}")

    return {
        "profit": profit,
        "hands":  hands,
        "wins":   wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": win_rate,
        "goal_hit": profit >= goal,
        "busted":   profit <= -bankroll,
    }


def run_multi(runs: int, bankroll: int, base_bet: int, goal: int, max_bet: int):
    """Run N sessions silently and print aggregate stats."""
    results = [run_session(bankroll, base_bet, goal, max_bet, verbose=False)
               for _ in range(runs)]

    goals_hit   = sum(1 for r in results if r["goal_hit"])
    busted      = sum(1 for r in results if r["busted"])
    avg_profit  = sum(r["profit"] for r in results) / runs
    avg_hands   = sum(r["hands"]  for r in results) / runs
    avg_wr      = sum(r["win_rate"] for r in results) / runs

    print(f"\n{'='*55}")
    print(f"  SIMULATION: {runs} sessions")
    print(f"  Bankroll: ${bankroll} | Base: ${base_bet} | Goal: +${goal} | Max: ${max_bet}")
    print(f"{'='*55}")
    print(f"  Goal hit:    {goals_hit}/{runs} ({goals_hit/runs*100:.1f}%)")
    print(f"  Busted:      {busted}/{runs}  ({busted/runs*100:.1f}%)")
    print(f"  Avg profit:  ${avg_profit:+.2f}")
    print(f"  Avg hands:   {avg_hands:.1f}")
    print(f"  Avg win rate:{avg_wr:.1f}%")
    print(f"{'='*55}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Blackjack Martingale Simulation")
    parser.add_argument("--bankroll", type=int, default=5000)
    parser.add_argument("--base-bet", type=int, default=50)
    parser.add_argument("--goal",     type=int, default=300)
    parser.add_argument("--max-bet",  type=int, default=1600)
    parser.add_argument("--hands",    type=int, default=0,
                        help="Max hands to play (0=unlimited)")
    parser.add_argument("--runs",     type=int, default=1,
                        help="Number of sessions to simulate (>1 suppresses per-hand output)")
    args = parser.parse_args()

    if args.runs > 1:
        run_multi(args.runs, args.bankroll, args.base_bet, args.goal, args.max_bet)
    else:
        run_session(args.bankroll, args.base_bet, args.goal, args.max_bet, verbose=True)


if __name__ == "__main__":
    main()
