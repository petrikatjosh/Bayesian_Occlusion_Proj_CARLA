# Bayesian Safety Controller for CARLA

A probabilistic safety controller for autonomous vehicles designed to handle **sensor occlusion** and **uncertainty**. This project implements a Recursive Bayesian Filter to estimate collision risk in "blind spots" (e.g., pedestrians hidden behind trucks) where deterministic AEB (Automatic Emergency Braking) often fails.

## Demo

**Video Demonstration:** [https://youtu.be/UJPgLf01mFs](https://youtu.be/UJPgLf01mFs?si=eCZaPCiRyMzWw651)

---

## Key Capabilities

- **Recursive Bayesian Filter:** Replaces instantaneous distance checks with a belief update loop to smooth noisy sensor data and maintain risk estimates over time.
- **Occlusion Handling:** Maintains a "memory" of risk when targets are briefly occluded, preventing the car from accelerating recklessly into blind zones.
- **Hysteresis Control:** Implements a "Creep Mode" (max 2.75 m/s) to safely navigate high-risk zones without control oscillation (stop-go jerking).
- **Geometric Radar:** Uses dot-product cone detection to identify pedestrians directly in the vehicle's path.

---

## Test Scenario: "Deathtrap"

A Tesla Model 3 approaches an intersection at 6 m/s while a delivery truck occludes a pedestrian crossing. The controller must:

1. **Detect** the occlusion risk (truck blocking view)
2. **Enter Creep Mode** before the intersection
3. **Emergency brake** when pedestrian becomes visible
4. **Recover** and safely depart

**Outcome:** Zero collisions across all test runs.

### Scenario Layout
| Actor | Start Position | Behavior |
|-------|---------------|----------|
| Ego Vehicle (Tesla Model 3) | x=-47, y=13 | Controller-driven, target 6 m/s |
| Occluder (Truck) | x=-52, y=16 | Constant velocity (-1.6 m/s) |
| Pedestrian | x=-65.75, y=21 | Crosses at 2.1 m/s toward y=35 |
| Intersection | x=-66, y=13 | Danger zone |

---

## System Architecture

The controller operates on a modified version of "Algorithm 3" from Wang et al. (2025):

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Perception    │────▶│  Bayesian Filter │────▶│ Decision Logic  │
│  (Sensors)      │     │  (Risk Update)   │     │ (Control Output)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │                        │
   - Velocity              - Prior Risk              - Emergency Stop
   - Dist to Truck         - Likelihood              - Creep Mode
   - Pedestrian Visible    - Posterior Risk          - Cruise Control
```

### Bayesian Update Rule

```
P(risk_k) = α · L(observation) + (1 - α) · P(risk_{k-1})
```

Where:
- `α = 0.4` — Learning rate (trust in new data vs. prior belief)
- `L(observation) = σ(-0.8 · margin)` — Sigmoid likelihood function
- `margin = distance - stopping_dist - paranoia_buffer`
- `stopping_dist = v² / (2 · μ · g)` — Physics-based stopping distance

### Decision Thresholds

| Risk Level | Threshold | Action |
|------------|-----------|--------|
| Critical | > 0.85 | Emergency Stop (full brake) |
| High | 0.60 - 0.85 | Creep Mode (max 2.75 m/s) |
| Normal | < 0.60 | Cruise Control (target 6.0 m/s) |

---

## Performance Results

### Phase Analysis

| Phase | Speed Mean (m/s) | Speed Std | Risk Mean | Risk Max | Steps |
|-------|------------------|-----------|-----------|----------|-------|
| Approach | 2.30 | 2.06 | 0.14 | 0.54 | 28 |
| Creep (Pre-Detection) | 5.29 | 0.32 | 0.77 | 0.84 | 11 |
| Emergency Stop | 0.00 | 0.00 | 0.98 | 1.00 | 50 |
| Recovery/Creep | 3.44 | 1.31 | 0.61 | 0.82 | 134 |
| Safe Departure | 6.00 | 0.19 | 0.02 | 0.09 | 25 |

### Key Metrics

| Metric | Value |
|--------|-------|
| Total Timesteps | 248 |
| Speed Variance (Creep Mode) | 1.83 |
| Speed Variance (Normal Mode) | 0.03 |
| Stability Ratio | **52.5x more stable** in normal operation |
| Collisions | **0** |

---

## Analysis Visualizations

### Temporal Behavior Analysis
![Time Series Analysis](figures/time_series_analysis.png)

*Shows the five distinct phases: Approach → Creep → Emergency Stop → Recovery → Safe Departure*

### Risk Distribution
![Risk Distribution](figures/risk_distribution.png)

*Histogram of risk values during operation, showing clear separation between safe and dangerous states*

### Variable Correlations
![Scatter Matrix](figures/scatter_matrix.png)

*Correlation analysis between Distance, Speed, Safety Margin, and Risk*

### System Performance
![Research Metrics](figures/research_metrics.png)

*Processing latency (~5ms average) and cross-track error over simulation time*

---

## Project Structure

```
├── bayesian_safety_controller.py   # Core Bayesian filter + control logic
├── deathtrap_with_radar.py         # CARLA scenario runner
├── metrics_logger.py               # Data collection for analysis
├── risk_log.csv                    # Output: timestep-by-timestep data
├── README.md                       # This file
└── figures/                        # Generated analysis plots
    ├── time_series_analysis.png
    ├── risk_distribution.png
    ├── scatter_matrix.png
    └── research_metrics.png
```

---

## Tech Stack

- **Simulator:** CARLA 0.9.15
- **Language:** Python 3.7+
- **Libraries:** `carla`, `numpy`, `opencv-python`, `matplotlib`

---

## Installation & Usage

### Prerequisites

1. Install CARLA 0.9.15 ([Installation Guide](https://carla.readthedocs.io/en/0.9.15/start_quickstart/))
2. Install Python dependencies:
   ```bash
   pip install numpy opencv-python matplotlib
   ```

### Running the Simulation

1. Launch CARLA server (Town 10):
   ```bash
   ./CarlaUE4.sh -quality-level=Low
   ```

2. In a separate terminal, run the scenario:
   ```bash
   python deathtrap_with_radar.py
   ```

3. Observe the simulation in the CARLA window and the ego camera feed in OpenCV.

### Output

- **Terminal:** Live time, position, and speed readout
- **CSV:** `risk_log.csv` with per-timestep data for analysis
- **Visual:** In-world debug text showing Risk, Status, Stopping Distance, and Safety Margin

---

## Design Decisions

### Why Bayesian Filtering?
Traditional AEB systems use instantaneous sensor readings, which fail catastrophically when a target is briefly occluded. The Bayesian filter maintains a **belief state** that decays gradually, providing a safety buffer during sensor dropouts.

### Passing Mode Logic
Added `prior_risk < 0.5` check to the passing detection logic. Without this, the car would incorrectly classify "stuck behind truck" as "passing truck" because both have `dist_to_truck < 5m`. The prior risk check ensures we only activate passing mode when we're genuinely confident, not when we're already scared.

### Creep Speed Cap (2.75 m/s)
Empirically tuned to balance:
- **Forward progress:** Allows the vehicle to clear the danger zone
- **Stopping capability:** At 2.75 m/s with μ=0.5, stopping distance ≈ 0.77m
- **Reaction time:** Gives ~5m of visibility at 15m detection range

### Hysteresis Gap (0.60 – 0.85)
The gap between "start creeping" (0.60) and "emergency stop" (0.85) prevents oscillation. Without this, the controller would rapidly alternate between braking and accelerating near the threshold.

### Paranoia Buffer (4.0m)
Added to stopping distance calculations as a safety margin for:
- Sensor noise and latency
- Actuator response time
- Road surface uncertainty

---

## Current Limitations

- **Lateral Logic:** The system uses a velocity-based heuristic to distinguish between "tailgating" and "passing." Future iterations will implement geometric raycasting for robust lateral state estimation.

- **Single Occluder:** Currently optimized for one occluding vehicle. Multi-occluder scenarios would require tracking multiple risk sources.

- **Fixed Thresholds:** Risk thresholds are manually tuned. Adaptive threshold learning could improve generalization.

- **No Prediction:** The pedestrian trajectory is not predicted—only current position is used. Adding a Kalman filter for pedestrian motion prediction would improve anticipation.

---

## Future Work

1. **Multi-Object Tracking:** Extend Bayesian filter to track multiple occluders and pedestrians
2. **Learned Thresholds:** Use reinforcement learning to adapt risk thresholds to different scenarios
3. **Trajectory Prediction:** Integrate pedestrian motion prediction for earlier intervention
4. **Real Sensor Integration:** Replace ground-truth positions with LiDAR/camera perception pipeline

---

## References

This project is an implementation and adaptation of the methods proposed in:

- **Wang, H., et al. (2025).** "Safe Driving in Occluded Environments" — arXiv preprint arXiv:2510.13114

**Specific Adaptations:**
- Adapted "Algorithm 3" (Risk Belief Update) with sigmoid likelihood function
- Added kinematic constraints (stopping distance physics)
- Implemented hysteresis controller to stabilize behavior within CARLA physics engine
- Added "Creep Mode" for cautious navigation through high-risk zones

---

## License

This project is for research and educational purposes.

---

## Acknowledgments

- CARLA Simulator team for the open-source autonomous driving platform
- Wang et al. for the theoretical foundation on occlusion-aware safety control
