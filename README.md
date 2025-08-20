<img width="500" height="500" alt="Untitled design (1)" src="https://github.com/user-attachments/assets/58770abf-07a2-4e51-ac7b-3ad82d6d8aaa" />

# Kelemvor’s Scales
**Encounter Monte Carlo + Auto-Tune (Crunchy Crits)**

Balance D&D 5e boss fights by simulating entire combats, not just average DPR. Get pacing guardrails (no steamrolls, no slogs), lethality estimates, and an auto-tuner that hits your target time-to-kill.

> *Design goal:* “Perilous but fair.” Median drama without coin-flip swing or endless grinds.

---
<img width="1594" height="991" alt="image" src="https://github.com/user-attachments/assets/38983781-240d-4a7a-9050-8c6a3201e0af" />


# Quick UI Tour

## 👥 Party & DPR

Enter PCs’ AC, HP, and save bonuses (STR/DEX/CON/INT/WIS/CHA).

Choose damage input mode:

Manual Effective DPR (enter your own per-round average)

Nova→Effective (enter “Nova DPR”, attack bonus, target AC, crit ratio, uptime)

## 🧰 Boss Kit

Add each attack: Type (attack/save), to-hit or DC, damage dice, uses/round, melee flag.

Optional: Lair (avg dmg, #targets, cadence), Recharge (e.g., 5-6, avg dmg, #targets).

Rider: on-hit effect that grants advantage next round or reduces target AC; duration in rounds.

## 📈 Deterministic DPR

Fast, average-based snapshot of boss damage versus each PC.

## ⏳ Boss TTD

Computes time to boss defeat from total incoming effective DPR, resistance, and regen.

## 🎯 Boss→PC MC

Monte Carlo of boss damage into a single PC over N rounds (useful for burst safety checks).

## ⚔️ Encounter MC

Full fight simulation with Trials, Max Rounds, Initiative, Party DPR CV, and Use Nova→Effective DPR toggle.

Auto-Tune (HP): set target median rounds and TPK cap; click Auto-Tune HP.

Outcome Summary + Survival Curve + TTK Distribution.

How to read the numbers (plain language)

Median TTK: the “typical” fight length. Aim for 3–5 rounds unless you like marathons.

p10–p90: middle 80% of outcomes.

p10 too low → too many steamrolls.

p90 too high → slog risk.

TPK Probability: fights where all PCs drop before the boss dies.

PCs down at victory: how bruising a win is (mean and p90).

Guardrails: compare the outputs to your thresholds (fast/slow caps, K-down target, TPK cap).

The graphs (what they mean)
Survival curve 
𝑆(𝑡)=𝑃(TTK>𝑡)
S(t)=P(TTK>t)

A step that drops at each round boundary.

Read tails directly:

𝑃(TTK≤2)=1−𝑆(2)
P(TTK≤2)=1−S(2) (steamroll frequency)

𝑃(TTK≥7)=𝑆(6)
P(TTK≥7)=S(6) (slog frequency)

The round where it crosses 0.5 is the median.

Long, shallow tail? Slogs. Cliff-like drop? Consistent pacing.

TTK distribution

A bar-like histogram (TTK is discrete: 3, 4, 5, …).

Spike heights ≈ how often fights end on that round.

Bimodal shape → the fight swings between two regimes (e.g., “alpha-strike” vs “attrition”).
Adjust kit/initiative/riders to smooth it.

## The math (lightly)

Monte Carlo: simulate thousands of fights with dice randomness. Summarize outcomes (medians, percentiles, probabilities).

Damage variance (Party DPR CV): we sample each PC’s per-round damage from a Gamma distribution with:

mean = your effective DPR,

CV (coefficient of variation) you set; shape = 1/CV², scale = mean/shape.

Hit chance: attack roll vs AC with nat-1 auto miss, nat-20 auto hit (crit).

Crunchy crits: on crit, damage = max dice + one normal roll + modifier once.

Save-for-half: expected damage = 0.5+0.5⋅𝑃(fail) times average damage.

Initiative: if the boss acts first, PCs might lose actions that round if they drop before swinging.

Resist/regen/THP: applied after damage sampling each round.

Spread targets (N): each round, the boss randomly selects up to N distinct living PCs, and spreads attacks among that pool (uniformly).

Balancing playbook

Pick your vibe: set Target median (e.g., 4.0).

Run Encounter MC → check p10–p90:

Want fewer steamrolls? Raise early boss sturdiness (resist/HP), reduce party CV, or tweak initiative.

Want fewer slogs? Lower boss HP/resist slightly, add lair/recharge that closes fights.

Check lethality: P(≥2 PCs down) near your taste (say ~20%); TPK ≤ 5%.

Auto-Tune HP to lock the median; iterate DPR and riders to shape the tails.

Re-run until guardrails show ✓.

---

## TL;DR

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
