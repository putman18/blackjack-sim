"""
Diagnostic 2: Play through a full hand, screenshot each state,
dump game frame globals to find card state variables.
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://www.247blackjack.com/"
OUT = Path(__file__).parent.parent.parent / ".tmp"
OUT.mkdir(exist_ok=True)

def click_canvas(page, box, rx, ry, label=""):
    x = box["x"] + box["width"]  * rx
    y = box["y"] + box["height"] * ry
    print(f"  Click {label} ({rx},{ry}) -> page ({x:.0f},{y:.0f})")
    page.mouse.click(x, y)

def shot(page, name):
    p = OUT / f"d2_{name}.png"
    page.screenshot(path=str(p))
    print(f"  Screenshot: {p.name}")

def dump_globals(page):
    """Try to find game state in the game iframe."""
    for frame in page.frames:
        if "game/frame" in frame.url:
            print(f"\n  [Game frame globals]")
            try:
                keys = frame.evaluate("""
                () => {
                    return Object.keys(window).filter(k => {
                        try {
                            const v = window[k];
                            return v !== null && v !== undefined &&
                                   typeof v !== 'function' &&
                                   !['NaN','Infinity','undefined'].includes(k);
                        } catch(e) { return false; }
                    });
                }
                """)
                print(f"  Window keys ({len(keys)}): {keys[:40]}")

                # Try to find objects with card/hand/player/dealer properties
                interesting = frame.evaluate("""
                () => {
                    const result = {};
                    for (const k of Object.keys(window)) {
                        try {
                            const v = window[k];
                            if (v && typeof v === 'object') {
                                const s = JSON.stringify(v).substring(0, 200);
                                if (/card|hand|player|dealer|score|total|bet|chips/i.test(s)) {
                                    result[k] = s;
                                }
                            }
                        } catch(e) {}
                    }
                    return result;
                }
                """)
                if interesting:
                    print(f"  Interesting globals:")
                    for k, v in interesting.items():
                        print(f"    {k}: {v[:120]}")
                else:
                    print("  No obviously interesting globals found.")
            except Exception as e:
                print(f"  Error: {e}")
            break

def sample_canvas_pixels(page, label):
    """Sample pixels from game canvas using WebGL readPixels."""
    for frame in page.frames:
        if "game/frame" in frame.url:
            try:
                result = frame.evaluate("""
                () => {
                    const canvas = document.querySelector('canvas');
                    if (!canvas) return 'no canvas';
                    const gl = canvas.getContext('webgl') ||
                               canvas.getContext('experimental-webgl');
                    if (!gl) return 'no webgl';
                    const w = canvas.width, h = canvas.height;
                    const samples = {};
                    // Sample key areas
                    const areas = {
                        'center_top':  [w*0.5,  h*0.15],
                        'center_mid':  [w*0.5,  h*0.40],
                        'result_area': [w*0.5,  h*0.25],
                        'bottom_ctr':  [w*0.5,  h*0.85],
                        'chip1':       [w*0.05, h*0.57],
                        'chip10':      [w*0.05, h*0.65],
                    };
                    const buf = new Uint8Array(4);
                    for (const [name, [x, y]] of Object.entries(areas)) {
                        // WebGL y is flipped
                        gl.readPixels(Math.floor(x), Math.floor(h - y),
                                      1, 1, gl.RGBA, gl.UNSIGNED_BYTE, buf);
                        samples[name] = {r:buf[0], g:buf[1], b:buf[2], a:buf[3]};
                    }
                    return {w, h, samples};
                }
                """)
                print(f"  [{label}] WebGL pixels: {result}")
            except Exception as e:
                print(f"  [{label}] WebGL error: {e}")
            break

with sync_playwright() as p:
    # Inject preserveDrawingBuffer before any page loads
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
    )
    # Override getContext to force preserveDrawingBuffer
    context.add_init_script("""
    const _origGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attrs) {
        if (type === 'webgl' || type === 'webgl2' || type === 'experimental-webgl') {
            attrs = Object.assign({}, attrs || {}, {preserveDrawingBuffer: true});
        }
        return _origGetContext.call(this, type, attrs);
    };
    """)
    page = context.new_page()

    print("1. Loading page...")
    page.goto(URL, timeout=30000)
    page.wait_for_load_state("networkidle", timeout=20000)
    time.sleep(3)
    shot(page, "1_loaded")

    # Get canvas box
    fl = page.frame_locator("#app-player-cjs-frame")
    canvas = fl.locator("canvas").first
    box = canvas.bounding_box(timeout=5000)
    print(f"   Canvas: {box}")

    print("\n2. Clicking PLAY...")
    click_canvas(page, box, 0.24, 0.73, "PLAY")
    time.sleep(4)
    shot(page, "2_after_play")
    sample_canvas_pixels(page, "after_play")

    print("\n3. Clicking $10 chip...")
    click_canvas(page, box, 0.05, 0.65, "$10 chip")
    time.sleep(1)
    shot(page, "3_after_chip")
    sample_canvas_pixels(page, "after_chip")

    print("\n4. Looking for DEAL button - trying various positions...")
    # Try clicking betting circle first (center of table)
    click_canvas(page, box, 0.50, 0.70, "table center")
    time.sleep(1)
    shot(page, "4_after_table_click")

    # Try deal at bottom center
    click_canvas(page, box, 0.50, 0.88, "deal bottom center")
    time.sleep(2)
    shot(page, "5_after_deal_attempt")
    sample_canvas_pixels(page, "after_deal")

    print("\n5. Dump globals...")
    dump_globals(page)

    time.sleep(3)
    shot(page, "6_game_state")
    sample_canvas_pixels(page, "game_state")

    print("\n6. Try HIT at various positions...")
    for rx, ry in [(0.36, 0.88), (0.25, 0.88), (0.40, 0.88)]:
        click_canvas(page, box, rx, ry, f"hit?")
        time.sleep(0.5)
    shot(page, "7_after_hit_attempts")

    time.sleep(5)
    shot(page, "8_final_state")
    sample_canvas_pixels(page, "final")

    print("\nDone. All screenshots in .tmp/")
    browser.close()
