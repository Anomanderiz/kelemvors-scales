# Kelemvor’s Scales
**Encounter Monte Carlo + Auto-Tune (Crunchy Crits)**

Balance D&D 5e boss fights by simulating entire combats, not just average DPR. Get pacing guardrails (no steamrolls, no slogs), lethality estimates, and an auto-tuner that hits your target time-to-kill.

> *Design goal:* “Perilous but fair.” Median drama without coin-flip swing or endless grinds.

---

## TL;DR for non-technical users

- **Download & run (Windows):** grab the latest release, unzip, double-click `KelemvorsScales.exe`.
- **Basic workflow (5 minutes):**
  1. **Party & DPR** tab: enter each PC’s **AC**, **HP**, and **save bonuses**; add either **Manual DPR** or **Nova→Effective** rows.
  2. **Boss Kit** tab: add the boss’s attacks (to-hit/DC, damage, uses/round, melee?), plus **lair**, **recharge**, and any **on-hit rider**.
  3. **⚔️ Encounter MC** tab: set **Trials** (10–30k), **Max Rounds** (~12), **Initiative** (random), and the **Party DPR CV** (variance, default 0.60).
  4. Click **Run Encounter Simulation**. Read **Median TTK**, **p10–p90**, **TPK%**, and **PCs down**.
  5. If pacing’s off, hit **Auto-Tune HP** to land on your target **median** rounds.

---

## Features

- **Encounter Monte Carlo:** full fights, round-by-round: initiative, attacks, saves, crits (house-rule: *max dice + one rolled*), lair cadence, recharge chance, riders, per-target THP/round, regen/resistance, PCs dropping.
- **Auto-Tune (HP):** pick a target **median TTK** and optional **TPK cap**; the tuner searches HP and verifies with a full simulation.
- **Guardrail read-outs:** configurable thresholds with ✓/✗:
  - `P(TTK ≤ fast) ≤ cap` (avoid steamrolls)
  - `P(TTK ≥ slow) ≤ cap` (avoid slogs)
  - `P(≥ K PCs down at victory) ≈ target` (lethality band)
  - `P(TPK) ≤ cap`
- **Charts:** **Survival curve** (risk/percentiles) and **TTK distribution** (shape/modes).
- **Targeting that makes sense:** “Spread across N” samples uniformly from **all living PCs** each round (no list-order bias).
- **Crunchy crits:** crit = *max dice + one rolled* (modifier once) for attack rolls; save-based effects don’t crit (RAW).

---

## Install

### Option A — Download a release (Windows)
1. Head to **Releases** on this repo.
2. Download `KelemvorsScales-win64.zip`.
3. Unzip anywhere you like; run `KelemvorsScales.exe`.

> **Note:** Windows Defender sometimes grumbles about unsigned PyInstaller apps. If it blocks you:
> - Prefer `More info → Run anyway`, or
> - Add an **exclusion** for the app folder (safer than turning Defender off).
> - We do **not** recommend disabling AV system-wide.

### Option B — Run from source (Windows/macOS/Linux)
```bash
python -m venv .venv
# Activate the venv (Windows)
.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
python boss_balance_desktop_encounter_v5.py
