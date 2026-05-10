# Recursive Risk Estimator for Occlusion-Aware Autonomous Driving in CARLA

I built a probabilistic safety controller that handles sensor occlusion in autonomous driving scenarios. The core problem: deterministic AEB systems fail catastrophically when a pedestrian is hidden behind a truck because they rely on instantaneous sensor readings. The moment the pedestrian disappears from the sensor, the car assumes the coast is clear and accelerates. I replaced that logic with a recursive risk estimator that maintains a continuous risk belief over time, decaying gradually rather than snapping to zero.

**Methodological note:** The risk estimator uses an exponential moving average with a sigmoid-shaped likelihood function — a lightweight heuristic inspired by Bayesian filtering, not a full Bayesian posterior update over a probability distribution. This design choice prioritized real-time simplicity for a proof-of-concept. Extending this to a formally grounded probabilistic framework (e.g., particle filters, or probabilistic safety certificates as in [Wang et al., 2025](https://arxiv.org/abs/2510.13114)) is a primary direction for future work.

Demo Video: https://youtu.be/VopOavB_F6M

---

## The Problem I Solved

Standard AEB checks distance to obstacles every frame. If distance is less than stopping distance, brake. Otherwise, accelerate. This works fine in open environments. However, it breaks down in occlusion scenarios because the obstacle literally does not exist in the sensor data until it is too late.

I wanted to build a controller that could reason about what it cannot see. Specifically, I needed the car to slow down when approaching a truck that might be hiding something, even though the sensors report nothing dangerous.

---

## The Scenario

I set up a worst-case test in CARLA called the Occluded Intersection Scenario. A Tesla Model 3 drives at 6 m/s toward an intersection. A delivery truck in the adjacent lane blocks the view of a pedestrian who is about to cross. The pedestrian starts at y=21, walking toward y=35 at 2.1 m/s. The intersection is at x=-66. The car starts at x=-47.

| Actor | Start Position | Behavior |
|-------|---------------|----------|
| Ego Vehicle (Tesla Model 3) | x=-47, y=13 | Controller-driven, target 6 m/s |
| Occluder (Truck) | x=-52, y=16 | Constant velocity (-1.6 m/s) |
| Pedestrian | x=-65.75, y=21 | Crosses at 2.1 m/s toward y=35 |
| Intersection | x=-66, y=13 | Danger zone |

The timing is deliberately tight. If the car maintains 6 m/s, it will hit the pedestrian. If it brakes too early, it fails the efficiency requirement. The controller has to thread the needle: slow down enough to stop in time once the pedestrian becomes visible, but not so much that it crawls unnecessarily.

I ran this scenario repeatedly and achieved zero collisions across all test runs.

---

## How the Risk Estimator Works

The estimator maintains a scalar risk belief that updates every timestep. I compute a likelihood based on the current safety margin, then blend it with the prior using a learning rate alpha. This is an exponential moving average, not a Bayesian posterior update — there is no explicit prior distribution, no normalization, and no latent state being inferred. The sigmoid likelihood and temporal smoothing produce behavior that resembles belief tracking, but the mathematical foundation is closer to a leaky integrator with a nonlinear input.

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
<img width="1400" height="1200" alt="timeseriesanalysis" src="https://github.com/user-attachments/assets/5982b866-5115-448f-9d8f-9e419f62dc6e" />


This plot shows the five phases in sequence. You can see the risk spike at pedestrian detection, the speed drop to zero during emergency stop, and the gradual recovery afterward. 

### Risk Distribution
<img width="1500" height="750" alt="risk_distribution" src="https://github.com/user-attachments/assets/a81a043e-cac4-4513-a1ff-503f63fd2b7e" />


This histogram reports the empirical timestep distribution of the recursive risk estimate during non-saturated operation. The saturated visible-threat reflex plateau (`Risk = 1.0`, `Speed = 0`, `Safety_Margin = -10`) is excluded because those samples are produced after the pedestrian is directly detected and the hard safety override takes control, rather than by the normal recursive risk estimator. The emergency-stop event is still shown in the temporal behavior plot and phase table; this histogram isolates the estimator's graded behavior outside the reflex-saturated state.

In this run, the filtered set contains approximately 200 non-saturated samples from `risk_log.csv`: 55.5% in normal operation (`risk ≤ 0.60`), 42.5% in the cautious creep band (`0.60 < risk ≤ 0.85`), and 2.0% in the non-saturated critical band (`0.85 < risk < 1.00`). This is the desired structure: most non-saturated timesteps are either low-risk cruise/departure or bounded occlusion-aware creep, with only a few critical-threshold samples before the visible-threat reflex layer takes over. After fixing the endpoint of the scenario before the next intersection at x = -95, the risk distribution became finalized at roughly these numbers.

Because the filtered set contains roughly 200 samples, one additional timestep above the critical threshold changes the displayed percentage by about 0.5%. Small run-to-run values such as 0.0%, 0.5%, 1.0%, or 2.0% should therefore be interpreted as threshold-edge timing differences, not as changes in the actual emergency-stop duration.


### Risk Correlations / Safety-Margin Structure
<img width="2100" height="900" alt="risk_correlations" src="https://github.com/user-attachments/assets/5a556ef8-695b-4108-9aea-bd68e63a1c6c" />


### Phase-Colored Scatter Matrix
<img width="1800" height="1800" alt="scatter_matrix_phased" src="https://github.com/user-attachments/assets/b0447afb-b345-44cc-b2d1-26764f929925" />


### System Latency and Cross-Track Error
<img width="1000" height="800" alt="system_latency_and_CTE" src="https://github.com/user-attachments/assets/5250b487-4eec-4aff-ac08-75974629fbf9" />



The latency spike at t=0 is initialization overhead. Steady-state latency sits around 5ms. Cross-track error increases at the end because the controller is longitudinal-only. Lateral control was out of scope for this project.

---

## Limitations and Research Directions

The limitations below motivated my interest in formally grounded probabilistic safety frameworks — particularly probabilistic invariance methods that provide long-term safety guarantees without the over-conservatism of worst-case approaches.

### From Heuristic Risk Tracking to Formal Safety Certificates

The core limitation: the current risk estimator is a heuristic with empirically tuned thresholds (0.60 for creep, 0.85 for emergency stop). These values were found through trial and error on the Occluded Intersection Scenario test. They work here. They might not generalize. More fundamentally, the exponential moving average update provides no formal guarantee that long-term collision probability stays below a desired tolerance. Replacing this with a proper probabilistic safety certificate — where linear constraints on control actions confine latent risk probability within a provable bound — is the most important extension of this work.

### From Scalar Risk to Distributional Prediction

The estimator tracks a single scalar. A more principled approach would maintain a full probability distribution over possible hidden-agent states and future trajectories. I plan to explore diffusion-based trajectory prediction to generate diverse plausible futures across multiple scenarios, producing calibrated probability distributions that could feed into a formal safety framework rather than a hand-tuned sigmoid.

### Additional Practical Limitations

- **Idealized perception:** Uses simulation ground truth for pedestrian positioning. I intentionally bypassed a noisy perception pipeline to isolate control logic performance. A real deployment would require a particle filter or similar to handle position uncertainty.
- **Latency Integration** While the system logs computation latency at approximately 5ms, the current stopping distance formula assumes idealized, instantaneous actuation. Future iterations should explicitly factor this latency into the safety margin calculation as d_reaction = v * t_latency to prevent overestimating the available braking distance at higher speeds. At 6 m/s with 5ms latency, this adds only 0.03 meters, but the principle matters for faster vehicles.
- **Single-source occlusion:** The estimator tracks one risk source. Scaling to complex urban environments requires multi-agent tracking via grid-based occupancy filtering.
- **Reactive pedestrian handling:** No trajectory prediction — the system reacts to instantaneous state rather than projecting future intersection points.
- **Heuristic passing logic:** The overtaking override assumes the occluder maintains its lane. A lateral TTC metric would be more robust.
- **Hardcoded friction (μ=0.5):** A friction observer would adapt braking distance for varying road conditions.

---

## Project Structure

```
├── risk_safety_controller.py       # Core risk estimator + control logic
├── occluded_intersection.py        # CARLA scenario runner (occluded intersection)
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
python occluded_intersection.py
```

The simulation ends automatically when the car reaches x=-95. Terminal shows live time, position, and speed. The CARLA window shows an overhead view with debug text floating above the car indicating risk level and control state.

---

## References

Wang et al. (2025). Safe Driving in Occluded Environments. arXiv:2510.13114.

The risk estimation approach in this project was motivated by their goal of maintaining a continuous safety probability estimate across timesteps — specifically, the idea that a controller should not treat occlusion as binary (safe/unsafe) but should track a persistent risk quantity that informs control decisions over time. The key difference is that my implementation uses a heuristic exponential moving average with a closed-form braking distance formula, rather than the formal probabilistic invariance framework and Monte Carlo risk estimation they develop. Extending this work to incorporate their safety certificate formulation is a primary research direction.
