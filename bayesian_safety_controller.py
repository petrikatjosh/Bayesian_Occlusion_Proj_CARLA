import glob
import os
import sys
import numpy as np

# --- CARLA SETUP (Keep this so it finds the library) ---
try:
    sys.path.append(glob.glob('../../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    try:
        sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
            sys.version_info.major,
            sys.version_info.minor,
            'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
    except IndexError:
        pass

import carla

class SniperController:
    """
    Implements the "Modified Algorithm 3" from Wang et al. (2025).
    Replaces static Monte Carlo tables with a Recursive Bayesian Filter.
    """
    def __init__(self, ego_vehicle):
        self.vehicle = ego_vehicle
        
        # --- BAYESIAN FILTER STATE ---
        self.prior_risk = 0.1  # P(x_k-1): Initial belief
        # self.alpha = 0.2       # Learning Rate: How much we trust new data vs old belief
        # increased alpha (0.2 -> 0.4) so it learns faster
        self.alpha = 0.4
        self.risk_threshold = 0.6 # The "Safety Certificate" limit (1 - epsilon)

        # --- LOGGING SETUP ---
        # Opens a file named 'risk_log.csv' in the same folder
        self.log_file = open('risk_log.csv', 'w')
        # Write the headers for the columns
        self.log_file.write("Step,Dist_to_Truck,Speed,Stopping_Dist,Safety_Margin,Risk\n")
        self.step_counter = 0

    def get_control_action(self, dist_to_int, dist_to_occluder, is_pedestrian_visible):
        """
        THIS IS ALGORITHM 3 (The Control Loop)
        1. Measure State
        2. Update Bayesian Belief (Risk Estimation)
        3. Apply Safety Constraints
        """

        # --- LAYER 0: THE REFLEX (System 1) ---
        # If we physically see the pedestrian in front of us, STOP.
        # This prevents the "Philosopher Crash" where we think but don't act.
        control = carla.VehicleControl()

        # --- LAYER 0: THE REFLEX (System 1) ---
        if is_pedestrian_visible:
            print("*** VISIBLE THREAT DETECTED -> EMERGENCY BRAKE ***")
            control.throttle = 0.0
            control.brake = 1.0
            
            # --- FIX: Log and Draw BEFORE returning ---
            
            # 1. Update the HUD
            # We pass Risk=1.0 (Certainty). 
            # We rely on 'custom_status' to ensure the Red Text appears.
            self._draw_live_debug(risk=1.0, stopping_dist=0.0, safety_margin=-10.0, custom_status="!!! PEDESTRIAN DETECTED !!!")

            # 2. Force write to CSV
            self.step_counter += 1
            # Log as: Risk=1.0000 (Mathematically Correct)
            log_line = f"{self.step_counter},0.00,0.00,0.00,-10.00,1.0000\n"
            self.log_file.write(log_line)
            self.log_file.flush()

            return control
        
        # 1. Measure Physics (Inputs)
        v = self.vehicle.get_velocity()
        speed_ms = np.sqrt(v.x**2 + v.y**2)
        
        # 2. Estimate Risk (The "Bayesian" Upgrade)
        # This replaces the old "heuristic" function
        current_risk = self._update_bayesian_belief(speed_ms, dist_to_occluder)
        
        # # 3. Decision Logic (The Safety Certificate)
        # control = carla.VehicleControl()
        
        # # If Risk > Threshold, we must intervene (Algorithm 3, Line 10)
        # if current_risk > self.risk_threshold:
        #     print(f"*** RISK HIGH ({current_risk:.2f}) -> BRAKING ***")
        #     control.throttle = 0.0
        #     control.brake = 1.0  # Emergency Stop

        # 3. Decision Logic
        if current_risk > self.risk_threshold:
            
            # --- [NEW] SPLIT LOGIC: CREEP vs. PANIC ---
            
            # CASE A: CRITICAL DANGER (Risk > 0.85)
            # This covers your "Radar" concern. If risk spikes high, we kill the creep.
            if current_risk > 0.85:
                 print(f"*** RISK CRITICAL ({current_risk:.2f}) -> FULL STOP ***")
                 control.throttle = 0.0
                 control.brake = 1.0
            
            # CASE B: CAUTIOUS CREEP (Risk 0.60 to 0.85)
            # We allow movement, but cap the speed.
            else:
                target_creep_speed = 2.75 # m/s
                
                if speed_ms < target_creep_speed:
                    # We are below creep limit -> Gentle Throttle
                    print(f"*** RISK HIGH ({current_risk:.2f}) -> CREEPING ({speed_ms:.1f}/{target_creep_speed} m/s) ***")
                    control.throttle = 0.3
                    control.brake = 0.0
                else:
                    # We are going too fast for a creep -> Coast/Feather Brake
                    # (Note: We do NOT slam brake here, preventing the oscillation)
                    control.throttle = 0.0
                    control.brake = 0.0 # Just coast to slow down
        
        else:
            # Nominal Controller (Cruise Control)
            target_speed = 6.0 # m/s
            if speed_ms < target_speed:
                control.throttle = 0.6
                control.brake = 0.0
            else:
                control.throttle = 0.0
                control.brake = 0.0

        # --- 4. VISUAL DEBUGGING ---
        self._draw_live_debug(current_risk, self.debug_stopping_dist, self.debug_margin)
                
        return control

    # Updated bayesian belief function

    def _update_bayesian_belief(self, speed, d_occ):
        # --- 1. INPUT CORRECTION (With Panic Check) ---
        effective_distance = d_occ 
        
        # [THE FIX] Added: 'and self.prior_risk < 0.5'
        # We only activate "Passing Mode" if we aren't ALREADY scared.
        # If we were braking (Risk > 0.5), we are stuck behind it, not passing it.
        if d_occ < 5.0 and speed > 2.0 and self.prior_risk < 0.5:
            effective_distance = 50.0
            
            # Update Debugs
            self.debug_stopping_dist = 0.0 
            self.debug_margin = 99.9 

        # ... (Rest of the function stays exactly the same) ...
        safe_stopping_dist = (speed ** 2) / (2 * 0.5 * 9.81)
        PARANOIA_BUFFER = 4.0 
        
        # Calculate Margin using the EFFECTIVE distance
        safety_margin = effective_distance - (safe_stopping_dist + PARANOIA_BUFFER)
        
        if not (d_occ < 5.0 and speed > 2.0 and self.prior_risk < 0.5):
             self.debug_stopping_dist = safe_stopping_dist
             self.debug_margin = safety_margin

        # ... (Keep the rest of your Bayesian logic below) ...
        
        # --- 3. BAYESIAN UPDATE (Runs Normally!) ---
        # Sigmoid Function
        # Since margin is huge (when passing), likelihood drops to ~0.0 naturally.
        current_likelihood = 1.0 / (1.0 + np.exp(0.8 * safety_margin))
        
        # The Filter Update
        # This is better than 'return 0.0' because 'self.prior_risk' helps smooth the transition.
        self.alpha = 0.4
        posterior_risk = (self.alpha * current_likelihood) + ((1 - self.alpha) * self.prior_risk)
        self.prior_risk = posterior_risk
        
        # --- 4. LOGGING ---
        self.step_counter += 1
        # We log BOTH the real sensor data (d_occ) AND the risk result
        # This lets you see: "Dist was 4m, but Risk dropped to 0.01 because of Speed"
        log_line = f"{self.step_counter},{d_occ:.2f},{speed:.2f},{safe_stopping_dist:.2f},{safety_margin:.2f},{posterior_risk:.4f}\n"
        self.log_file.write(log_line)
        self.log_file.flush()
        
        return posterior_risk


    def _draw_live_debug(self, risk, stopping_dist, safety_margin, custom_status=None):
        """
        Draws floating text above the car in the 3D simulation window.
        """
        world = self.vehicle.get_world()
        loc = self.vehicle.get_location()
        
        # Shift text 2 meters up so it floats above the roof
        loc.z += 2.0 

        # 1. Check for PASSING first (Specific String)
        if custom_status == "PASSING MODE" or custom_status == "PASSING":
            color = carla.Color(0, 255, 255) # CYAN
            status = "PASSING MODE"

        # 2. Check for any OTHER custom status (Pedestrian/Emergency)
        elif custom_status: 
            color = carla.Color(255, 128, 0) # SAFETY ORANGE (or White)
            status = custom_status # This will print "PEDESTRIAN DETECTED" or whatever you sent

        # 3. If no custom status, check Risk
        elif risk > self.risk_threshold:
            color = carla.Color(255, 255, 0) # YELLOW
            status = "BRAKING (RISK HIGH)"

        # 4. Default to Cruising
        else:
            color = carla.Color(0, 255, 0) # GREEN
            status = "CRUISING"

        debug_text = (
            f"STATUS: {status}\n"
            f"Risk: {risk:.2f} (Thresh: {self.risk_threshold})\n"
            f"StopDist: {stopping_dist:.1f}m\n"
            f"Margin: {safety_margin:.1f}m"
        )

        # Draw the string in the world (Life_time=0.1s so it updates flicker-free)
        world.debug.draw_string(loc, debug_text, draw_shadow=True, 
                                color=color, life_time=0.0515)