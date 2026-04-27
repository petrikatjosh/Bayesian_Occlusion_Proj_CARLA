import carla
import random
import time
import math
import numpy as np
import cv2
import queue

# from updated_safety_controller import SniperController
from risk_safety_controller import SniperController
from metrics_logger import ResearchLogger


def main():
    try:
        # 1. Connect to CARLA
        client = carla.Client('localhost', 2000)
        client.set_timeout(10.0)
        world = client.get_world()
        map = world.get_map()
        bp_lib = world.get_blueprint_library()

        # 2. Setup Spectator
        spectator = world.get_spectator()

        # 3. Spawn Ego Vehicle
        ego_bp = bp_lib.find('vehicle.tesla.model3')
        # start_loc = carla.Location(x=-50.5, y=13, z=1.0)
        start_loc = carla.Location(x=-47, y=13, z=1.0) # spawning the car further back

        # Move back 9 meters to give it a "Run Up"
        # start_loc = carla.Location(x=-30, y=13, z=1.0)
        ego_transform = carla.Transform(start_loc, carla.Rotation(yaw=180))
        ego_vehicle = world.spawn_actor(ego_bp, ego_transform)

        # --- SNIPER MODIFICATION 1: DISABLE PHYSICS HACK ---
        # COMMENT THIS OUT! We want the controller to drive, not magic physics.
        # ego_vehicle.set_target_velocity(carla.Vector3D(x=-7.55, y=0, z=0)) 
        
        # 4. Spawn Occluder (Truck)
        truck_bp = bp_lib.find('vehicle.carlamotors.carlacola')
        truck_loc = carla.Location(x=-52, y=16, z=1.0)
        truck_transform = carla.Transform(truck_loc, carla.Rotation(yaw=180))
        truck = world.spawn_actor(truck_bp, truck_transform)
        
        # Truck keeps moving (constant velocity is fine for the dummy truck)
        # truck.set_target_velocity(carla.Vector3D(x=-2.7, y=0, z=0))

        # attempting slower speed to create more realistic scenerio
        truck.set_target_velocity(carla.Vector3D(x=-1.6, y=0, z=0))

        # 5. Spawn Walker
        walker_bp = bp_lib.find('walker.pedestrian.0001')
        # walker_loc = carla.Location(x=-65.75, y=20.11, z=0.25)
        # Old: y=20.11
        # New: y=21.0 (Push them 1 meter deeper into the shadow)
        walker_loc = carla.Location(x=-65.75, y=21.0, z=0.25)
        walker_transform = carla.Transform(walker_loc, carla.Rotation(yaw=90))
        walker = world.spawn_actor(walker_bp, walker_transform)

        # --- CAMERA SETUP (Kept exactly as you had it) ---
        image_queue = queue.Queue()
        camera_bp = bp_lib.find('sensor.camera.rgb')
        camera_bp.set_attribute('image_size_x', '1280') # <-- New (16:9 HD Standard)
        camera_bp.set_attribute('image_size_y', '720')  # <-- New
        camera_bp.set_attribute('fov', '90')
        camera_transform = carla.Transform(carla.Location(x=-0.3, y=-0.4, z=1.2))
        camera = world.spawn_actor(camera_bp, camera_transform, attach_to=ego_vehicle)
        camera.listen(lambda data: image_queue.put(data))

        time.sleep(1.0) # Physics settle

        # Walker Destination
        target_loc = carla.Location(x=-65.96, y=35.89, z=0) 

        
        # --- SNIPER MODIFICATION 2: TURN ON THE BRAIN ---
        # Initialize the controller you wrote in safety_controller.py
        brain = SniperController(ego_vehicle)
        
        # Define the "Danger Zone" (The intersection/crossing point)
        # Based on the walker coordinates, the crossing is around x=-66
        intersection_loc = carla.Location(x=-66, y=13, z=0)

        print("Starting Simulation with CONTROLLER...")

        logger = ResearchLogger()

        # --- TIMER SETUP ---
        sim_start_time = time.time() 
        
        while True:
            loop_start = time.time() # <--- 1. START CLOCK
            # --- 1. WALKER CONTROL (Keep this existing logic) ---
            current_loc = walker.get_location()
            direction_vector = current_loc - target_loc 
            length = math.sqrt(direction_vector.x**2 + direction_vector.y**2)
            
            if length > 0.5:
                direction_norm = carla.Vector3D(direction_vector.x / length, direction_vector.y / length, 0.0)
                control = carla.WalkerControl()
                control.speed = 2.1
                control.direction = direction_norm 
                control.jump = False
                walker.apply_control(control)
            else:
                walker.apply_control(carla.WalkerControl(speed=0.0))

            # --- SNIPER MODIFICATION 3: THE CONTROL LOOP ---
            
            # A. Get Data
            ego_loc = ego_vehicle.get_location()
            truck_loc = truck.get_location()

            # --- [NEW CODE START] ---

            # Get the car's current transform (Location + Rotation)
            car_transform = ego_vehicle.get_transform()


            # Force the Spectator to follow the car from the sky
            spectator_transform = carla.Transform(
                ego_loc + carla.Location(z=35), # Height of 35 meters
                carla.Rotation(pitch=-90, yaw=180, roll=0) # Pitch -90 looks straight down
            )
            spectator.set_transform(spectator_transform)
            # --- [NEW CODE END] ---
            
            # B. Calculate Distances
            dist_to_int = ego_loc.distance(intersection_loc)
            dist_to_occluder = ego_loc.distance(truck_loc)
            
            # --- C. NEW "GEOMETRIC RADAR" REFLEX (This replaces your old Reflex block) ---
            ped_loc = walker.get_location()
            
            # 1. Vector Math Setup
            ego_transform = ego_vehicle.get_transform()
            ego_forward = ego_transform.get_forward_vector() # The direction car is facing
            
            # Vector from Car -> Pedestrian
            vec_to_ped = ped_loc - ego_loc
            dist_to_ped = math.sqrt(vec_to_ped.x**2 + vec_to_ped.y**2)

            is_pedestrian_blocking = False

            # 2. The Logic: "Are they close AND in front?"
            if dist_to_ped < 15.0:
                # Normalize the vector to the pedestrian
                vec_to_ped_norm = carla.Vector3D(
                    vec_to_ped.x / dist_to_ped, 
                    vec_to_ped.y / dist_to_ped, 
                    0.0
                )
                
                # DOT PRODUCT: Calculates alignment (-1.0 to 1.0)
                # 1.0 = Dead Ahead. 0.0 = Exactly to the side.
                dot_prod = ego_forward.x * vec_to_ped_norm.x + ego_forward.y * vec_to_ped_norm.y
                
                # 3. The Cone Check (0.95 is roughly +/- 18 degrees)
                if dot_prod > 0.95:
                     is_pedestrian_blocking = True
                     # Draw a Red Line to visualize the "Radar Lock"
                     world.debug.draw_line(ego_loc, ped_loc, thickness=0.1, color=carla.Color(255,0,0), life_time=0.1)

            # --- D. ASK THE BRAIN ---
            # Now passing 'is_pedestrian_blocking' instead of the old variable
            safe_control = brain.get_control_action(dist_to_int, dist_to_occluder, is_pedestrian_blocking)
            
            # E. Execute Order
            ego_vehicle.apply_control(safe_control)

            # --- CAMERA VISUALIZATION (Fixed for Real-Time) ---
            if not image_queue.empty():
                # DRAIN THE QUEUE: Throw away old images to get the latest one
                while not image_queue.empty():
                    image = image_queue.get()
                
                # Now 'image' holds the most recent frame.
                i = np.array(image.raw_data)
                i2 = i.reshape((720, 1280, 4))
                im_display = i2[:, :, :3]
                cv2.imshow("Ego Vehicle Front Camera", im_display)
                cv2.waitKey(1)

            logger.log_step(ego_vehicle, map, loop_start) # <--- 2. LOG DATA

            # --- LIVE TIMER DISPLAY ---                                                      
            elapsed_time = time.time() - sim_start_time                                       
            # Get current speed for display                                                   
            vel = ego_vehicle.get_velocity()                                                  
            current_speed = math.sqrt(vel.x**2 + vel.y**2)                                    
            # Print on same line using \r (carriage return)                                   
            print(f"\rTime: {elapsed_time:6.2f}s | Pos X: {ego_loc.x:7.2f} | Speed: {current_speed:4.2f} m/s", end="", flush=True)  

            # --- AUTO-END CONDITION ---
            # End scenario when ego vehicle passes x=-95 (well past the intersection at x=-66)
            if ego_loc.x < -95:
                print("\n=== SCENARIO COMPLETE: Vehicle passed end point (x=-95) ===")
                break

            # Important: Add World Tick if running in synchronous mode
            time.sleep(0.05)

    finally:
        print("\nDestroying actors...")
        if 'ego_vehicle' in locals(): ego_vehicle.destroy()
        if 'truck' in locals(): truck.destroy()
        if 'walker' in locals(): walker.destroy()
        if 'camera' in locals(): 
            camera.stop()
            camera.destroy()
            cv2.destroyAllWindows()

if __name__ == '__main__':
    main()