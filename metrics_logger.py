import csv
import time
import math
import carla

class ResearchLogger:
    def __init__(self, filename='research_data.csv'):
        self.filename = filename
        self.start_time = time.time()
        self.headers = ['Timestamp', 'Latency_ms', 'Cross_Track_Error', 'Velocity_kmh']
        
        # Initialize the CSV
        with open(self.filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)

    def log_step(self, vehicle, world_map, loop_start_time):
        # 1. Calculate Latency (Processing time for this frame)
        current_time = time.time()
        latency = (current_time - loop_start_time) * 1000 # in ms

        # 2. Calculate Cross Track Error (CTE)
        # Distance between your car and the center of the lane (Ground Truth)
        vehicle_loc = vehicle.get_location()
        waypoint = world_map.get_waypoint(vehicle_loc, project_to_road=True)
        cte = vehicle_loc.distance(waypoint.transform.location)

        # 3. Get Velocity
        v = vehicle.get_velocity()
        kmh = (3.6 * math.sqrt(v.x**2 + v.y**2 + v.z**2))

        # Write to CSV
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([current_time - self.start_time, latency, cte, kmh])