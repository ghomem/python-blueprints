#!/usr/bin/env python3
"""
Extract Kreis-level (NUTS-3) price per m² from the BBSR Tableau story
"Wohnflächenpreise für gebrauchte Eigentumswohnungen" (story point "Kreiskarte").

The server has data download disabled (toolbar only offers Image/PDF/PowerPoint),
but the map is rendered client-side, so the data travels in the vizql JSON
responses. We drive headless Chromium with a normal browser user agent, capture
those responses via the Chrome DevTools Protocol, and decode Tableau's
dictionary-encoded columns.

Usage:
    python3 bbsr_kreise.py [--years 2023 2024 2025] [--out kreise_preise.csv] [--geometry kreise_geometry.csv]
"""
import argparse, json, os, re, sys, time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

URL = ("https://tableau.bbsr.bund.de/t/bbr/views/S07_Preise_gebrauchte_ETW/"
       "WohnflchenpreisefrgebrauchtefreistehendeEin-undZweifamilienhuser"
       "?%3Aembed=y&%3AisGuestRedirectFromVizportal=y")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
STORY_POINT = "Kreiskarte"
PRICE_COL = "AGG(mittlerer Wohnflächenpreis Bestandimmobilien (Gew Round))"
CLASS_COL = "AGG(mittlerer Wohnflächenpreis Bestandimmobilien (Gew Round Klassen))"


# ---------------------------------------------------------------- decoding
def find(o, key, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                yield path + "/" + k, v
            yield from find(v, key, path + "/" + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from find(v, key, f"{path}[{i}]")


class DictState:
    """Tableau sends dictionary-encoded columns. The first response of a layout
    carries segment 0; each later command response (e.g. a filter change) adds a
    new numbered segment, and value/alias indices refer to the concatenation of
    all segments received so far, in segment-id order. Keep that state here."""

    def __init__(self):
        self.segments = {}

    def update(self, resp):
        for _, dd in find(resp, "dataDictionary"):
            segs = dd.get("dataSegments")
            if segs is None and "presModelHolder" in dd:  # bootstrap shape
                segs = dd["presModelHolder"]["genDataDictionaryPresModel"]["dataSegments"]
            for sid, seg in (segs or {}).items():
                self.segments[int(sid)] = seg

    def lists(self):
        out = {}
        for sid in sorted(self.segments):
            for col in self.segments[sid]["dataColumns"]:
                out.setdefault(col["dataType"], []).extend(col["dataValues"])
        return out


def decode_tables(resp, state):
    """Decode every vizData pane in a vqlCmdResponse into DataFrames."""
    state.update(resp)
    segs = state.lists()
    if not segs:
        return {}
    out = {}
    for path, vd in find(resp, "vizData"):
        pcd = vd.get("paneColumnsData") or {}
        cols = pcd.get("vizDataColumns", [])
        for pi, pane in enumerate(pcd.get("paneColumnsList", [])):
            frame = {}
            for c in cols:
                cap = c.get("fieldCaption")
                if not cap:
                    continue
                for p, ci in zip(c["paneIndices"], c["columnIndices"]):
                    if p != pi:
                        continue
                    vpc = pane["vizPaneColumns"][ci]
                    dt = c["dataType"]
                    ali, val = vpc["aliasIndices"], vpc["valueIndices"]
                    if dt == "spatial" and ali:        # polygons index the spatial dictionary
                        vals = [segs["spatial"][i] for i in ali]
                    elif ali and ali[0] >= 0:          # display alias (string)
                        vals = [segs["cstring"][i] for i in ali]
                    elif val:                          # raw typed value
                        vals = [segs[dt][i] for i in val]
                    elif ali:                          # formatted string only
                        vals = [segs["cstring"][-i - 1] for i in ali]
                    else:
                        continue
                    frame[cap] = vals
            if frame:
                n = max(len(v) for v in frame.values())
                frame = {k: v for k, v in frame.items() if len(v) == n}
                out[f"{path}|pane{pi}"] = pd.DataFrame(frame)
    return out


def kreis_table(resp, state):
    """Pick the pane that holds the Kreis marks and tidy it."""
    for key, df in decode_tables(resp, state).items():
        if "Kreis" in df.columns and PRICE_COL in df.columns:
            df = df.rename(columns={
                "Kreis": "kreis",
                "Kreisfrei / Landkreis": "kreis_typ",
                "Daten gemeldet/geschätzt": "datenstatus",
                "YEAR(Jahr)": "jahr",
                PRICE_COL: "preis_eur_m2",
                CLASS_COL: "preisklasse",
                "Latitude (generated)": "lat",
                "Longitude (generated)": "lon",
                "COLLECT(Geometrie)": "geometry_wkt",
            })
            df["preis_eur_m2"] = pd.to_numeric(
                df["preis_eur_m2"].astype(str).str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False), errors="coerce")
            df["jahr"] = pd.to_numeric(df["jahr"], errors="coerce").astype("Int64")
            return df
    return None


# ---------------------------------------------------------------- browser
def make_driver():
    opts = Options()
    for b in ("/usr/bin/chromium-browser", "/usr/bin/chromium", "/snap/bin/chromium"):
        if os.path.exists(b):
            opts.binary_location = b
            break
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1600,1200")
    opts.add_argument(f"--user-agent={UA}")
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    d = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=opts)
    d.execute_cdp_cmd("Network.enable", {"maxResourceBufferSize": 256 * 1024 * 1024,
                                         "maxTotalBufferSize": 512 * 1024 * 1024})
    return d


def drain_vizql(d):
    """Return bodies of all vizql command/bootstrap responses logged since last call."""
    bodies = []
    for e in d.get_log("performance"):
        m = json.loads(e["message"])["message"]
        if m["method"] != "Network.responseReceived":
            continue
        u = m["params"]["response"]["url"]
        if "/vizql/t/" not in u:
            continue
        try:
            body = d.execute_cdp_cmd("Network.getResponseBody", {"requestId": m["params"]["requestId"]})["body"]
        except Exception:
            continue
        bodies.append((u, body))
    return bodies


def parse_body(body):
    """Bootstrap responses are 'len;json' chunks; command responses are plain JSON."""
    body = body.strip()
    if body.startswith("{"):
        return [json.loads(body)]
    objs, i = [], 0
    while i < len(body):
        m = re.match(r"(\d+);", body[i:])
        if not m:
            break
        n = int(m.group(1)); i += m.end()
        objs.append(json.loads(body[i:i + n])); i += n
    return objs


def latest_kreis_table(bodies, state):
    df = None
    for _, body in bodies:
        try:
            for obj in parse_body(body):
                t = kreis_table(obj, state)
                if t is not None:
                    df = t
        except Exception as ex:  # noqa
            print("  (skip body: %s)" % ex, file=sys.stderr)
    return df


def select_year(d, year):
    """Select a value in the 'Jahr' radio quick filter.

    Tableau's legacy dojo filter widget ignores synthetic mouse clicks in headless
    Chromium, but it honours keyboard input: focus the radio item and press Space.
    """
    items = [it for it in d.find_elements(By.CSS_SELECTOR, ".tab-quick-filter .FIItem[role=radio]")
             if it.is_displayed() and it.text.strip() == str(year)]
    if not items:
        return False
    it = items[0]
    d.execute_script("arguments[0].scrollIntoView(true); arguments[0].focus();", it)
    ActionChains(d).send_keys(Keys.SPACE).perform()
    for _ in range(20):
        time.sleep(0.5)
        if it.get_attribute("aria-checked") == "true":
            return True
    return it.get_attribute("aria-checked") == "true"


def wait_idle(d, seconds=6):
    time.sleep(seconds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="*", type=int, default=[2023, 2024, 2025])
    ap.add_argument("--out", default="kreise_preise.csv")
    ap.add_argument("--geometry", default=None, help="also write WKT polygons per Kreis to this CSV")
    args = ap.parse_args()

    d = make_driver()
    try:
        print("loading view …")
        d.get(URL)
        WebDriverWait(d, 90).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tabStoryPointCaption")))
        wait_idle(d, 5)
        state = DictState()
        drain_vizql(d)  # discard bootstrap (Subkreiskarte)

        cap = next(el for el in d.find_elements(By.CSS_SELECTOR, ".tabStoryPointCaption")
                   if el.text.strip() == STORY_POINT)
        cap.click()
        print(f"switched to story point '{STORY_POINT}'")
        wait_idle(d, 10)
        base = latest_kreis_table(drain_vizql(d), state)
        if base is None:
            sys.exit("could not find Kreis data in story point response")
        current_year = int(base["jahr"].iloc[0])
        print(f"  default year {current_year}: {len(base)} Kreise")
        frames = {current_year: base}
        geometry = base[["kreis", "kreis_typ", "geometry_wkt"]].copy() if "geometry_wkt" in base else None

        for y in args.years:
            if y in frames:
                continue
            if not select_year(d, y):
                print(f"  year {y}: radio not found, skipping")
                continue
            wait_idle(d, 8)
            t = latest_kreis_table(drain_vizql(d), state)
            if t is None or t.empty:
                print(f"  year {y}: no data in response")
                continue
            got = int(t["jahr"].iloc[0])
            print(f"  year {y}: {len(t)} Kreise (response says {got})")
            frames[got] = t
    finally:
        d.quit()

    df = pd.concat(frames.values(), ignore_index=True)
    keep = ["jahr", "kreis", "kreis_typ", "datenstatus", "preis_eur_m2", "preisklasse", "lat", "lon"]
    df = df[[c for c in keep if c in df.columns]].sort_values(["jahr", "kreis"]).reset_index(drop=True)
    df.to_csv(args.out, index=False)
    print(f"wrote {args.out}: {len(df)} rows, years {sorted(df['jahr'].dropna().unique().tolist())}")
    if args.geometry and geometry is not None:
        geometry.to_csv(args.geometry, index=False)
        print(f"wrote {args.geometry}: {len(geometry)} polygons (WKT)")


if __name__ == "__main__":
    main()
