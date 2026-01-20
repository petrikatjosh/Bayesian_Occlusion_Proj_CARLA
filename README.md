# Bayesian Safety Controller for CARLA

I built a probabilistic safety controller that handles sensor occlusion in autonomous driving scenarios. The core problem: deterministic AEB systems fail catastrophically when a pedestrian is hidden behind a truck because they rely on instantaneous sensor readings. The moment the pedestrian disappears from the sensor, the car assumes the coast is clear and accelerates. I replaced that logic with a Recursive Bayesian Filter that maintains a belief state over time, decaying gradually rather than snapping to zero.

Demo: https://youtu.be/UJPgLf01mFs

---

## The Problem I Solved

Standard AEB checks distance to obstacles every frame. If distance is less than stopping distance, brake. Otherwise, accelerate. This works fine in open environments. However, it breaks down in occlusion scenarios because the obstacle literally does not exist in the sensor data until it is too late.

I wanted to build a controller that could reason about what it cannot see. Specifically, I needed the car to slow down when approaching a truck that might be hiding something, even though the sensors report nothing dangerous.

---

## The Scenario

I set up a worst-case test in CARLA called the Deathtrap. A Tesla Model 3 drives at 6 m/s toward an intersection. A delivery truck in the adjacent lane blocks the view of a pedestrian who is about to cross. The pedestrian starts at y=21, walking toward y=35 at 2.1 m/s. The intersection is at x=-66. The car starts at x=-47.

| Actor | Start Position | Behavior |
|-------|---------------|----------|
| Ego Vehicle (Tesla Model 3) | x=-47, y=13 | Controller-driven, target 6 m/s |
| Occluder (Truck) | x=-52, y=16 | Constant velocity (-1.6 m/s) |
| Pedestrian | x=-65.75, y=21 | Crosses at 2.1 m/s toward y=35 |
| Intersection | x=-66, y=13 | Danger zone |

The timing is deliberately tight. If the car maintains 6 m/s, it will hit the pedestrian. If it brakes too early, it fails the efficiency requirement. The controller has to thread the needle: slow down enough to stop in time once the pedestrian becomes visible, but not so much that it crawls unnecessarily.

I ran this scenario repeatedly and achieved zero collisions across all test runs.

---

## How the Bayesian Filter Works

The filter maintains a prior risk value that updates every timestep. I compute a likelihood based on the current safety margin, then blend it with the prior using a learning rate alpha.

The update rule:

```
posterior_risk = alpha * likelihood + (1 - alpha) * prior_risk
```

I set alpha to 0.4 after some experimentation. Higher values made the filter too twitchy. Lower values made it too sluggish to respond to sudden changes.

The likelihood comes from a sigmoid function applied to the safety margin:

```
likelihood = 1 / (1 + exp(0.8 * margin))
margin = distance_to_truck - stopping_distance - paranoia_buffer
stopping_distance = v^2 / (2 * mu * g)
```

When the margin is large and positive, the likelihood drops toward zero. When the margin goes negative, meaning I cannot stop in time, the likelihood spikes toward one. The sigmoid gives me a smooth transition rather than a hard threshold.

I added a paranoia buffer of 4 meters to account for sensor noise, actuator lag, and my own uncertainty about the road surface friction coefficient. In retrospect, I probably should have made this adaptive based on speed, but the fixed value worked well enough for this scenario.

---

## The Control Logic

I split the decision space into three regions based on the posterior risk.

| Risk Level | Threshold | Action |
|------------|-----------|--------|
| Critical | > 0.85 | Emergency Stop (full brake) |
| High | 0.60 - 0.85 | Creep Mode (max 2.75 m/s) |
| Normal | < 0.60 | Cruise Control (target 6.0 m/s) |

Risk above 0.85 triggers an emergency stop. Full brake, zero throttle. This is the oh-no-I-see-the-pedestrian mode.

Risk between 0.60 and 0.85 triggers creep mode. I cap the speed at 2.75 m/s, which gives a stopping distance of about 0.77 meters at mu=0.5. This lets the car make forward progress while staying prepared to stop instantly.

Risk below 0.60 means cruise control. Target speed 6 m/s, gentle throttle.

The gap between 0.60 and 0.85 is intentional. Without it, the controller oscillated rapidly between braking and accelerating near the threshold. The hysteresis band fixed that completely.

---

## What Broke Along the Way

The first version had a nasty bug in the passing logic. I wanted the car to recognize when it was overtaking the truck versus when it was stuck behind it. My initial heuristic: if distance to truck is less than 5 meters and speed is above 2 m/s, we must be passing it, so ignore the occlusion risk.

This failed spectacularly. The car would approach the truck, enter creep mode correctly, then suddenly decide it was passing and accelerate directly into the danger zone. The problem was that creep mode itself satisfies speed above 2 m/s. Consequently, the car would creep, trigger passing mode, accelerate, re-enter creep mode, trigger passing mode again, and repeat.

I fixed it by adding a check on the prior risk. Passing mode only activates if prior_risk is below 0.5. If the car is already scared, it stays scared. This one-line fix eliminated the oscillation entirely.

The second major issue was the geometric radar for pedestrian detection. I needed to know if the pedestrian was directly in front of the car, not just nearby. I compute a dot product between the car's forward vector and the normalized vector to the pedestrian. If the dot product exceeds 0.95, roughly plus or minus 18 degrees, I flag the pedestrian as blocking.

Initially I set the threshold at 0.8, which was way too wide. The car would emergency brake when the pedestrian was still off to the side, well before any actual danger. Tightening to 0.95 fixed the false positives.

---

## Results

I logged every timestep to a CSV and ran analysis afterward. The scenario breaks down into five phases.

| Phase | Steps | Speed Mean (m/s) | Speed Std | Risk Mean | Risk Max |
|-------|-------|------------------|-----------|-----------|----------|
| Approach | 28 | 2.30 | 2.06 | 0.14 | 0.54 |
| Creep (Pre-Detection) | 11 | 5.29 | 0.32 | 0.77 | 0.84 |
| Emergency Stop | 50 | 0.00 | 0.00 | 0.98 | 1.00 |
| Recovery/Creep | 134 | 3.44 | 1.31 | 0.61 | 0.82 |
| Safe Departure | 25 | 6.00 | 0.19 | 0.02 | 0.09 |

The approach phase shows the car accelerating from standstill. Creep phase kicks in when risk climbs above 0.60 but the pedestrian is not yet visible—the car is slowing down preemptively based on occlusion risk alone. Emergency stop is exactly what it sounds like. Recovery takes the longest because the risk decays gradually as the car creeps through the danger zone. Safe departure is the return to normal cruise.

| Metric | Value |
|--------|-------|
| Total Timesteps | 248 |
| Speed Variance (Creep Mode) | 1.83 |
| Speed Variance (Normal Mode) | 0.03 |
| Stability Ratio | 52.5x more stable in normal operation |
| Collisions | 0 |

Speed variance in creep mode was 1.83. In normal cruise mode it was 0.03. That 52x difference shows the controller is stable when it should be stable and appropriately variable when navigating uncertainty.

Processing latency averaged around 5 milliseconds per loop iteration. Plenty fast for a 20 Hz control loop.

---

## Visualizations

### Temporal Behavior
img width="1400" height="1200" alt="timeseriesanalysis" src="https://github.com/user-attachments/assets/5982b866-5115-448f-9d8f-9e419f62dc6e" />


This plot shows the five phases in sequence. You can see the risk spike at pedestrian detection, the speed drop to zero during emergency stop, and the gradual recovery afterward. 

### Risk Distribution
<img width="1000" height="500" alt="riskdistribution" src="https://github.com/user-attachments/assets/fe5a8ddb-3d9a-424e-81f3-edecdbe0d602" />


The bimodal distribution is intentional. The controller spends most of its time either in safe cruise (risk near 0) or in cautious creep (risk 0.6-0.85). The spike at 0.8 represents the car's creep speed beside the truck in response to the potential occlusion threat.
### Variable Correlations
<img width="1200" height="1200" alt="variablecorrelations" src="https://github.com/user-attachments/assets/b38cdb0b-a6ff-4538-893e-199948acd106" />


### System Latency
<img width="1000" height="800" alt="system_latency_and_CTE" src="https://github.com/user-attachments/assets/5250b487-4eec-4aff-ac08-75974629fbf9" />



The latency spike at t=0 is initialization overhead. Steady-state latency sits around 5ms. Cross-track error increases at the end because the controller is longitudinal-only. Lateral control was out of scope for this project.

---

## What I Would Do Differently

The fixed thresholds bother me. I tuned 0.60 and 0.85 by trial and error on this one scenario. They might not generalize. A proper approach would learn these thresholds from data or adapt them online based on the environment.

The pedestrian detection uses ground truth position, which is cheating. In a real system I would need to run this through a perception pipeline with all its associated noise and latency. The Bayesian filter should help with that, but I have not tested it.

I only handle one occluder. Multiple trucks would require tracking multiple risk sources and somehow combining them. Probably a particle filter or separate Bayesian estimates that get fused.

The pedestrian trajectory is not predicted. I react to current position only. Adding a Kalman filter to estimate pedestrian velocity and project forward would let me brake earlier in ambiguous cases.

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

## Running It

Prerequisites: CARLA 0.9.15, Python 3.7+, numpy, opencv-python, matplotlib.

```bash
pip install numpy opencv-python matplotlib
```

Start CARLA server on Town 10:

```bash
./CarlaUE4.sh -quality-level=Low
```

In a separate terminal:

```bash
python deathtrap_with_radar.py
```

The simulation ends automatically when the car reaches x=-95. Terminal shows live time, position, and speed. The CARLA window shows an overhead view with debug text floating above the car indicating risk level and control state.

---

## References

Wang, H., et al. (2025). Safe Driving in Occluded Environments. arXiv:2510.13114.

I adapted their Algorithm 3 for risk belief updates, added kinematic stopping distance calculations, and implemented the hysteresis controller to prevent oscillation in the CARLA physics engine.
