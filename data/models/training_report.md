# Session-Generator Model Training Report

- Trained on: 30 sessions
- Skipped: 0

## Style classification (heuristic mapping)
- `sanfter_aufbau`: 9 sessions
- `crescendo`: 1 sessions
- `beat_drop`: 11 sessions
- `edging`: 5 sessions
- `ruin`: 4 sessions
- `endlos_tease`: 0 sessions

## Macro envelope sampler
- `sanfter_aufbau` n=9 — mean range [0.004..0.974], std range [0.010..0.319]
- `crescendo` n=1 — mean range [0.000..1.000], std range [0.060..0.060]
- `beat_drop` n=11 — mean range [0.009..0.977], std range [0.023..0.347]
- `edging` n=5 — mean range [0.160..0.942], std range [0.038..0.291]
- `ruin` n=4 — mean range [0.000..0.832], std range [0.010..0.347]
- `endlos_tease` n=0 (fallback) — mean range [0.200..0.499], std range [0.060..0.060]

## Markov model — cells with data vs fallback
- `sanfter_aufbau`: 74 cells with data / 246 fallback (out of 320 total prev-x-phase cells)
- `crescendo`: 0 cells with data / 320 fallback (out of 320 total prev-x-phase cells)
- `beat_drop`: 73 cells with data / 247 fallback (out of 320 total prev-x-phase cells)
- `edging`: 60 cells with data / 260 fallback (out of 320 total prev-x-phase cells)
- `ruin`: 35 cells with data / 285 fallback (out of 320 total prev-x-phase cells)
- `endlos_tease`: 0 cells with data / 320 fallback (out of 320 total prev-x-phase cells)

## 3 sample envelope realisations per style
### sanfter_aufbau
- Sample 1: (0s, 0.26), (436s, 0.80), (900s, 0.74), (1364s, 0.66), (1800s, 0.75), (2236s, 0.80), (2700s, 0.26)
- Sample 2: (0s, 0.27), (436s, 0.64), (900s, 0.80), (1364s, 0.80), (1800s, 0.80), (2236s, 0.75), (2700s, 0.25)
- Sample 3: (0s, 0.25), (436s, 0.59), (900s, 0.70), (1364s, 0.67), (1800s, 0.73), (2236s, 0.75), (2700s, 0.25)

### crescendo
- Sample 1: (0s, 0.25), (436s, 0.80), (900s, 0.78), (1364s, 0.79), (1800s, 0.80), (2236s, 0.80), (2700s, 0.25)
- Sample 2: (0s, 0.25), (436s, 0.73), (900s, 0.79), (1364s, 0.80), (1800s, 0.80), (2236s, 0.80), (2700s, 0.28)
- Sample 3: (0s, 0.29), (436s, 0.79), (900s, 0.74), (1364s, 0.80), (1800s, 0.78), (2236s, 0.80), (2700s, 0.25)

### beat_drop
- Sample 1: (0s, 0.28), (436s, 0.47), (900s, 0.73), (1364s, 0.76), (1800s, 0.80), (2236s, 0.80), (2700s, 0.25)
- Sample 2: (0s, 0.32), (436s, 0.65), (900s, 0.66), (1364s, 0.63), (1800s, 0.67), (2236s, 0.69), (2700s, 0.26)
- Sample 3: (0s, 0.27), (436s, 0.80), (900s, 0.68), (1364s, 0.70), (1800s, 0.80), (2236s, 0.54), (2700s, 0.26)

### edging
- Sample 1: (0s, 0.37), (436s, 0.65), (900s, 0.73), (1364s, 0.65), (1800s, 0.64), (2236s, 0.69), (2700s, 0.26)
- Sample 2: (0s, 0.28), (436s, 0.44), (900s, 0.74), (1364s, 0.71), (1800s, 0.70), (2236s, 0.75), (2700s, 0.53)
- Sample 3: (0s, 0.37), (436s, 0.54), (900s, 0.65), (1364s, 0.70), (1800s, 0.71), (2236s, 0.73), (2700s, 0.43)

### ruin
- Sample 1: (0s, 0.59), (436s, 0.57), (900s, 0.41), (1364s, 0.70), (1800s, 0.72), (2236s, 0.55), (2700s, 0.25)
- Sample 2: (0s, 0.29), (436s, 0.65), (900s, 0.62), (1364s, 0.70), (1800s, 0.71), (2236s, 0.49), (2700s, 0.25)
- Sample 3: (0s, 0.25), (436s, 0.58), (900s, 0.59), (1364s, 0.66), (1800s, 0.69), (2236s, 0.55), (2700s, 0.26)

### endlos_tease
- Sample 1: (0s, 0.35), (436s, 0.52), (900s, 0.52), (1364s, 0.49), (1800s, 0.50), (2236s, 0.52), (2700s, 0.50)
- Sample 2: (0s, 0.36), (436s, 0.46), (900s, 0.42), (1364s, 0.48), (1800s, 0.50), (2236s, 0.55), (2700s, 0.50)
- Sample 3: (0s, 0.30), (436s, 0.42), (900s, 0.47), (1364s, 0.46), (1800s, 0.57), (2236s, 0.55), (2700s, 0.48)

## Markov demo: sanfter_aufbau / phase=plateau / prev=V1 — top-5
- P8: 0.1849
- P3: 0.1233
- PMix1: 0.0959
- P12: 0.0479
- M6: 0.0411
