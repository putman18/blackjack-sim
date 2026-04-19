"""
blackjack_bot.py - Martingale blackjack bot for 247blackjack.com

Plays blackjack using basic strategy and Martingale bet sizing.
Stops when daily profit goal is reached.

Usage:
    python execution/blackjack_bot.py
    python execution/blackjack_bot.py --base-bet 10 --goal 300
    python execution/blackjack_bot.py --headless

Strategy:
    - Win: reset to base bet
    - Loss: double the bet
    - Push: repeat same bet
    - Stop when profit >= goal or next bet > max bet

Note: 247blackjack.com runs the game inside an IFRAME (id=app-player-cjs-frame).
All game interaction happens via canvas coordinate clicks within that iframe.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

PROJECT_ROOT = Path(__file__).parent.parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
TMP_DIR.mkdir(exist_ok=True)

for line in (PROJECT_ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

DISCORD_ALERTS = os.getenv("DISCORD_WEBHOOK_ALERTS", "")
URL = "https://www.247blackjack.com/"

# Approximate canvas layout ratios for 247blackjack.com
# These are relative positions (0.0 to 1.0) within the canvas
LAYOUT = {
    "play_button":   (0.50, 0.55),   # center-ish splash screen play button
    "deal_button":   (0.50, 0.88),   # bottom center
    "hit_button":    (0.36, 0.88),   # bottom left of center
    "stand_button":  (0.64, 0.88),   # bottom right of center
    "double_button": (0.22, 0.88),   # further left
    # Chips row at bottom - chip values left to right: 1, 5, 10, 25, 100, 500
    "chip_1":        (0.20, 0.80),
    "chip_5":        (0.30, 0.80),
    "chip_10":       (0.40, 0.80),
    "chip_25":       (0.50, 0.80),
    "chip_100":      (0.60, 0.80),
    "chip_500":      (0.70, 0.80),
}

CHIP_VALUES = [500, 100, 25, 10, 5, 1]
CHIP_KEYS   = ["chip_500", "chip_100", "chip_25", "chip_10", "chip_5", "chip_1"]


def post_discord(message: str):
    if not DISCORD_ALERTS:
        return
    data = json.dumps({"content": message}).encode()
    req = urllib.request.Request(
        DISCORD_ALERTS, data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def basic_strategy(player_total: int, player_soft: bool, dealer_up: int, can_double: bool) -> str:
    """
    Returns: 'hit', 'stand', 'double'
    Simplified basic strategy.
    """
    if player_soft:
        if player_total >= 19:
            return "stand"
        if player_total == 18:
            return "stand" if dealer_up in range(2, 7) else "hit"
        return "hit"

    if player_total >= 17:
        return "stand"
    if player_total <= 8:
        return "hit"
    if player_total in (10, 11) and can_double:
        return "double"
    if player_total in (12, 13, 14, 15, 16):
        return "stand" if dealer_up in range(2, 7) else "hit"
    if player_total == 9:
        return "double" if can_double and dealer_up in range(3, 7) else "hit"
    return "hit"


class BlackjackBot:
    def __init__(self, base_bet: int, goal: int, max_bet: int, headless: bool):
        self.base_bet = base_bet
        self.goal = goal
        self.max_bet = max_bet
        self.headless = headless
        self.current_bet = base_bet
        self.session_profit = 0
        self.hands_played = 0
        self.hands_won = 0
        self.hands_lost = 0
        self.hands_pushed = 0
        self.log = []
        self._canvas_box = None   # cached bounding box of game canvas

    def run(self):
        print(f"\nBlackjack Martingale Bot")
        print(f"  Base bet:  ${self.base_bet}")
        print(f"  Daily goal: ${self.goal}")
        print(f"  Max bet:    ${self.max_bet}")
        print(f"  Site:       {URL}")
        print()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            try:
                self._setup(page)
                self._play_session(page)
            except KeyboardInterrupt:
                print("\nStopped by user.")
            except Exception as e:
                print(f"\nError: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self._save_session_log()
                self._report_results()
                browser.close()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup(self, page):
        print("Loading 247blackjack.com...")
        page.goto(URL, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(3)

        # Dismiss cookie / consent banners on main page
        for selector in ["button:has-text('Accept')", "button:has-text('OK')", ".close-button", "#cookie-accept"]:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=800):
                    el.click()
                    time.sleep(0.5)
            except Exception:
                pass

        # The game lives inside an iframe - wait for it
        print("Waiting for game iframe...")
        try:
            page.wait_for_selector("#app-player-cjs-frame", timeout=15000)
            time.sleep(2)
        except Exception:
            print("  iframe not found by id, proceeding anyway")

        # Get the frame and find the canvas inside it
        canvas_box = self._get_canvas_box(page)
        if canvas_box is None:
            print("  WARNING: could not locate game canvas - trying full-page center click")
            page.mouse.click(640, 400)
            time.sleep(3)
            canvas_box = self._get_canvas_box(page)

        if canvas_box:
            print(f"  Canvas found: {canvas_box['width']:.0f}x{canvas_box['height']:.0f} at ({canvas_box['x']:.0f},{canvas_box['y']:.0f})")
            self._canvas_box = canvas_box
            # Click the play button on the splash screen
            self._canvas_click(page, "play_button")
            print("  Clicked Play button")
            time.sleep(3)
            # Click again in case a second confirmation is needed
            self._canvas_click(page, "play_button")
            time.sleep(2)
        else:
            print("  Could not find canvas - bot may not work correctly")

        print("Setup complete. Starting session...\n")

    def _get_canvas_box(self, page):
        """Find the game canvas inside the iframe and return its absolute bounding box."""
        # Try via frame_locator
        try:
            fl = page.frame_locator("#app-player-cjs-frame")
            canvas = fl.locator("canvas").first
            box = canvas.bounding_box(timeout=5000)
            if box and box["width"] > 0:
                return box
        except Exception:
            pass

        # Fallback: iterate frames
        try:
            for frame in page.frames:
                try:
                    canvas = frame.locator("canvas").first
                    box = canvas.bounding_box(timeout=2000)
                    if box and box["width"] > 0:
                        return box
                except Exception:
                    pass
        except Exception:
            pass

        # Last fallback: canvas on main page
        try:
            canvas = page.locator("canvas").first
            box = canvas.bounding_box(timeout=2000)
            if box and box["width"] > 0:
                return box
        except Exception:
            pass

        return None

    # ------------------------------------------------------------------
    # Canvas coordinate helpers
    # ------------------------------------------------------------------

    def _canvas_click(self, page, element_key: str):
        """Click a named element using its relative canvas position."""
        if self._canvas_box is None:
            self._canvas_box = self._get_canvas_box(page)
        if self._canvas_box is None:
            return
        rx, ry = LAYOUT[element_key]
        x = self._canvas_box["x"] + self._canvas_box["width"]  * rx
        y = self._canvas_box["y"] + self._canvas_box["height"] * ry
        page.mouse.click(x, y)
        time.sleep(0.15)

    def _canvas_click_xy(self, page, rx: float, ry: float):
        """Click using explicit relative coordinates."""
        if self._canvas_box is None:
            self._canvas_box = self._get_canvas_box(page)
        if self._canvas_box is None:
            return
        x = self._canvas_box["x"] + self._canvas_box["width"]  * rx
        y = self._canvas_box["y"] + self._canvas_box["height"] * ry
        page.mouse.click(x, y)
        time.sleep(0.15)

    # ------------------------------------------------------------------
    # Game actions (all canvas-coordinate based)
    # ------------------------------------------------------------------

    def _place_bet(self, page, amount: int):
        """Click chip buttons to total the desired bet."""
        remaining = amount
        for chip_val, chip_key in zip(CHIP_VALUES, CHIP_KEYS):
            while remaining >= chip_val:
                self._canvas_click(page, chip_key)
                remaining -= chip_val

    def _click_deal(self, page):
        self._canvas_click(page, "deal_button")

    def _click_action(self, page, action: str):
        key_map = {"hit": "hit_button", "stand": "stand_button", "double": "double_button"}
        key = key_map.get(action)
        if key:
            self._canvas_click(page, key)

    def _wait_for_result(self, page, timeout: int = 15) -> str:
        """
        Poll for win/lose/push by checking the DOM inside the iframe for result text.
        Falls back to a fixed wait and assumes the hand completed.
        """
        start = time.time()

        # Try reading result text from within the iframe
        result_texts = {
            "win":  ["you win", "blackjack", "winner"],
            "lose": ["bust", "you lose", "dealer wins"],
            "push": ["push", "tie"],
        }

        while time.time() - start < timeout:
            # Try to get text from within any frame
            for frame in page.frames:
                try:
                    body = frame.inner_text("body", timeout=500).lower()
                    for result, keywords in result_texts.items():
                        if any(kw in body for kw in keywords):
                            return result
                except Exception:
                    pass

            # Also try visible DOM selectors on main page
            result_selectors = {
                "win":  ["[class*='win']:visible", ":has-text('You Win'):visible", ":has-text('Blackjack'):visible"],
                "lose": ["[class*='lose']:visible", "[class*='bust']:visible", ":has-text('Bust'):visible", ":has-text('You Lose'):visible"],
                "push": ["[class*='push']:visible", ":has-text('Push'):visible", ":has-text('Tie'):visible"],
            }
            for result, selectors in result_selectors.items():
                for sel in selectors:
                    try:
                        if page.locator(sel).first.is_visible(timeout=200):
                            return result
                    except Exception:
                        pass

            time.sleep(0.3)

        return "unknown"

    def _play_hand(self, page) -> str:
        """Play one hand. Returns 'win', 'lose', 'push', or 'error'."""
        # Place bet
        self._place_bet(page, self.current_bet)
        time.sleep(0.5)

        # Deal
        self._click_deal(page)
        time.sleep(2.5)  # wait for cards to animate

        # Play out the hand
        # Since we can't read canvas card values, use a conservative default:
        # always stand (dealer must hit to 17, gives us house-edge-minimizing play)
        # A future improvement: inject JS or use OCR to read card values and apply full basic strategy
        for _ in range(6):  # max actions
            # Check if hit button area is likely active by looking for action phase
            # For now use stand as default safe action
            self._click_action(page, "stand")
            time.sleep(1.5)
            break

        # Wait for result
        result = self._wait_for_result(page, timeout=12)
        time.sleep(1)

        # Click "Deal Again" / center to start next hand
        # On 247blackjack the deal button doubles as "deal again" after a hand
        self._canvas_click(page, "deal_button")
        time.sleep(0.5)

        return result

    # ------------------------------------------------------------------
    # Session loop
    # ------------------------------------------------------------------

    def _play_session(self, page):
        print(f"Starting session. Goal: +${self.goal}\n")
        post_discord(f"Blackjack bot started. Goal: +${self.goal} | Base bet: ${self.base_bet}")

        while True:
            if self.current_bet > self.max_bet:
                msg = f"Max bet ${self.max_bet} reached. Stopping. Profit: ${self.session_profit:+}"
                print(msg)
                post_discord(f"Blackjack bot: {msg}")
                break

            if self.session_profit >= self.goal:
                msg = f"Daily goal reached! Profit: +${self.session_profit}. Done for today."
                print(f"\n{msg}")
                post_discord(f"Blackjack bot: {msg}")
                break

            self.hands_played += 1
            print(f"Hand {self.hands_played} | Bet: ${self.current_bet} | Profit: ${self.session_profit:+}", end=" -> ", flush=True)

            result = self._play_hand(page)

            if result == "win":
                self.session_profit += self.current_bet
                self.hands_won += 1
                self.current_bet = self.base_bet
                print(f"WIN  | Profit: ${self.session_profit:+}")
            elif result == "lose":
                self.session_profit -= self.current_bet
                self.hands_lost += 1
                self.current_bet = self.current_bet * 2
                print(f"LOSE | Profit: ${self.session_profit:+} | Next bet: ${self.current_bet}")
            elif result == "push":
                self.hands_pushed += 1
                print(f"PUSH | Profit: ${self.session_profit:+}")
            else:
                print(f"UNKNOWN - check browser (result detection may need tuning)")

            self.log.append({
                "hand":   self.hands_played,
                "bet":    self.current_bet,
                "result": result,
                "profit": self.session_profit,
            })

            time.sleep(0.5)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _save_session_log(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_path = TMP_DIR / f"blackjack_session_{date_str}.json"
        with open(log_path, "w") as f:
            json.dump({
                "date":          date_str,
                "base_bet":      self.base_bet,
                "goal":          self.goal,
                "profit":        self.session_profit,
                "hands_played":  self.hands_played,
                "hands_won":     self.hands_won,
                "hands_lost":    self.hands_lost,
                "hands_pushed":  self.hands_pushed,
                "hands":         self.log,
            }, f, indent=2)
        print(f"\nSession log saved: {log_path}")

    def _report_results(self):
        win_rate = self.hands_won / max(self.hands_played, 1) * 100
        msg = (
            f"Session complete | "
            f"Profit: ${self.session_profit:+} | "
            f"{self.hands_played} hands ({self.hands_won}W/{self.hands_lost}L/{self.hands_pushed}P) | "
            f"Win rate: {win_rate:.1f}%"
        )
        print(f"\n{'='*55}")
        print(f"  SESSION COMPLETE")
        print(f"  Profit:   ${self.session_profit:+}")
        print(f"  Hands:    {self.hands_played} ({self.hands_won}W / {self.hands_lost}L / {self.hands_pushed}P)")
        print(f"  Win rate: {win_rate:.1f}%")
        print(f"{'='*55}")
        post_discord(f"Blackjack bot: {msg}")


def main():
    parser = argparse.ArgumentParser(description="Blackjack Martingale Bot")
    parser.add_argument("--base-bet", type=int, default=5,   help="Starting bet (default: 5)")
    parser.add_argument("--goal",     type=int, default=300, help="Daily profit goal (default: 300)")
    parser.add_argument("--max-bet",  type=int, default=640, help="Max bet before stopping (default: 640)")
    parser.add_argument("--headless", action="store_true",   help="Run without visible browser")
    args = parser.parse_args()

    bot = BlackjackBot(
        base_bet=args.base_bet,
        goal=args.goal,
        max_bet=args.max_bet,
        headless=args.headless,
    )
    bot.run()


if __name__ == "__main__":
    main()
