"""Diagnostic: screenshots before/after clicking PLAY, dumps frame info."""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://www.247blackjack.com/"
OUT = Path(__file__).parent.parent.parent / ".tmp"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()

    print("Loading page...")
    page.goto(URL, timeout=30000)
    page.wait_for_load_state("networkidle", timeout=20000)
    time.sleep(3)

    # Screenshot 1: splash screen
    page.screenshot(path=str(OUT / "diag_1_splash.png"))
    print("Saved diag_1_splash.png")

    # Find canvas
    box = None
    try:
        fl = page.frame_locator("#app-player-cjs-frame")
        canvas = fl.locator("canvas").first
        box = canvas.bounding_box(timeout=5000)
        print(f"Canvas box: {box}")
    except Exception as e:
        print(f"iframe canvas error: {e}")
        try:
            canvas = page.locator("canvas").first
            box = canvas.bounding_box(timeout=3000)
            print(f"Main page canvas: {box}")
        except Exception as e2:
            print(f"No canvas found: {e2}")

    if box:
        # Click PLAY at left-center-bottom of canvas (approx 25%, 75%)
        for rx, ry in [(0.24, 0.73), (0.25, 0.75), (0.20, 0.70)]:
            cx = box["x"] + box["width"] * rx
            cy = box["y"] + box["height"] * ry
            print(f"\nClicking ({rx},{ry}) -> page ({cx:.0f},{cy:.0f})")
            page.mouse.click(cx, cy)
            time.sleep(2)
            shot = OUT / f"diag_click_{rx}_{ry}.png"
            page.screenshot(path=str(shot))
            print(f"Saved {shot.name}")

    print("\n--- Frame body text ---")
    for i, frame in enumerate(page.frames):
        try:
            body = frame.inner_text("body", timeout=1000)
            print(f"Frame[{i}] url={frame.url[:60]}")
            print(f"  body ({len(body)} chars): {repr(body[:300])}")
        except Exception as e:
            print(f"Frame[{i}]: {e}")

    print("\n--- Canvas pixel info ---")
    for i, frame in enumerate(page.frames):
        try:
            info = frame.evaluate("""
            () => {
                const c = document.querySelector('canvas');
                if (!c) return 'no canvas';
                const ctx = c.getContext('2d');
                if (!ctx) return 'no ctx';
                const w=c.width, h=c.height;
                // Sample grid of pixels
                const samples = [];
                for (let ry of [0.1, 0.2, 0.3, 0.5, 0.7, 0.8]) {
                    for (let rx of [0.1, 0.25, 0.5, 0.75, 0.9]) {
                        const d = ctx.getImageData(w*rx, h*ry, 1, 1).data;
                        samples.push({rx, ry, r:d[0], g:d[1], b:d[2]});
                    }
                }
                return {w, h, samples};
            }
            """)
            if info and info != 'no canvas' and info != 'no ctx':
                print(f"Frame[{i}]: canvas {info['w']}x{info['h']}")
                # Only print non-black pixels
                for s in info['samples']:
                    if s['r'] > 10 or s['g'] > 10 or s['b'] > 10:
                        print(f"  ({s['rx']},{s['ry']}) -> rgb({s['r']},{s['g']},{s['b']})")
        except Exception as e:
            print(f"Frame[{i}] canvas: {e}")

    print("\nDone. Check .tmp/ for screenshots.")
    input("Press Enter to close...")
    browser.close()
