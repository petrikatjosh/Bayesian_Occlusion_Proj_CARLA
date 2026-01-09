# Bayesian Safety Controller for CARLA

A probabilistic safety controller for autonomous vehicles designed to handle **sensor occlusion** and **uncertainty**. This project implements a Recursive Bayesian Filter to estimate collision risk in "blind spots" (e.g., pedestrians hidden behind trucks) where deterministic AEB (Automatic Emergency Braking) often fails.

## Demo Link
https://youtu.be/UJPgLf01mFs?si=eCZaPCiRyMzWw651

## ⚡ Key Capabilities
* **Recursive Bayesian Filter:** Replaces instantaneous distance checks with a belief update loop ![P(Risk|Observation)](https://latex.codecogs.com/svg.image?\fg{FFFFFF}P(\text{Risk}\mid\text{Observation}))

 to smooth noisy sensor data.
* **Occlusion Handling:** Maintains a "memory" of risk when targets are briefly occluded, preventing the car from accelerating recklessly into blind zones.
* **Hysteresis Control:** Implements a "Creep Mode" (max 2.75 m/s) to safely navigate high-risk zones without control oscillation (stop-go jerking).

## 🧠 System Architecture
The controller operates on a modified version of "Algorithm 3" (Wang et al., 2025):
1.  **Perception Layer:** Inputs vehicle velocity and LiDAR/Radar obstacle distance.
2.  **Belief Update:** A sigmoid likelihood function updates the `prior_risk` based on stopping distance margins.
3.  **Decision Logic:**
    * **Risk > 0.85:** Emergency Stop (Certain Threat).
    * **Risk 0.60 - 0.85:** Creep Mode (Speed limited to < 2.75 m/s).
    * **Risk < 0.60:** Nominal Cruise (PID Control).

## 🛠️ Tech Stack
* **Simulator:** CARLA 0.9.15
* **Language:** Python 3.7+
* **Libraries:** `carla`, `numpy`, `matplotlib` (for debug plotting)

## 🚀 How to Run
1.  Launch the CARLA Simulator (Town 10).
2.  Install the controller:
    ```bash
    bayesian_safety_controller.py
    ```
3.  In the same folder as the previous file, install the file and run:
    ```bash
    python deathtrap_with_radar.py
    ```

## ⚠️ Current Limitations
* **Lateral Logic:** The system currently uses a velocity-based heuristic to distinguish between "tailgating" and "passing." Future iterations will implement geometric raycasting for robust lateral state estimation.
* **Control Latency:** A deliberate 0.5s smoothing delay exists when exiting "Creep Mode" to ensure stability.

## 📚 References
This project is an implementation and adaptation of the methods proposed in:

* **Wang, H., et al. (2025).** "Safe Driving in Occluded Environments" arXiv preprint arXiv:2510.13114
* *Specific Adaptation:* Adapted "Algorithm 3" (Risk Belief Update), adding kinematic constraints and a hysteresis controller to stabilize behavior within the CARLA physics engine.
