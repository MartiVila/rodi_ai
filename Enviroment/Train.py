import pygame
from .EdgeType import EdgeType
from .TrafficManager import TrafficManager 

class TrainStatus:
    SENSE_RETARD = "ON TIME"     
    RETARD_MODERAT = "DELAYED" 
    AVARIAT = "BROKEN"           

class Train:
    ACCELERATION = 30.0   
    BRAKING = 80.0        
    SAFE_DISTANCE_PCT = 0.05 

    def __init__(self, agent, route_nodes, scheduled_times, start_time_sim):
        self.agent = agent
        self.route = route_nodes
        self.schedule = scheduled_times 
        self.start_time = start_time_sim 
        self.id = id(self) 

        self.route_index = 0
        self.node = self.route[0]
        self.target = self.route[1]
        
        self.current_time_accumulated = 0 
        self.status = TrainStatus.SENSE_RETARD
        
        self.delay_global = 0.0   
        self.segment_start_time = 0.0 
        self.finished = False
        self.progress = 0.0
        self.current_edge = None
        self.current_speed_kmh = 0.0 
        self.collision_detected = False

        self.is_yielding = False       
        self.waiting_for_track_fix = False 
        self.edge_just_finished = None 
        self.last_log_state = "IDLE"   
        
        self.is_in_siding = False      
        self.siding_entry_time = 0.0   
        self.siding_wait_duration = 0.0 

        print(f"[TRAIN {self.id}] SPAWNED at Node {self.node.id}")
        self.setup_segment()

    def setup_segment(self):
        """
        Decides which track to take.
        STRICT ENTRY GUARD: Will NOT enter if track is occupied or broken.
        """
        if self.target.id in self.node.neighbors:
            possible_edges = self.node.neighbors[self.target.id]
            
            valid_edge = None
            
            # Agent preference + Fallbacks
            state = self.get_state(possible_edges)
            preferred_idx = self.agent.choose_action(state)
            prioritized_indices = [preferred_idx] + [i for i in range(len(possible_edges)) if i != preferred_idx]
            
            for idx in prioritized_indices:
                edge = possible_edges[idx]
                
                # Check 1: Is it BROKEN?
                has_alert = TrafficManager.check_alert(self.node.id, self.target.id, edge.track_id)
                
                # Check 2: Is it OCCUPIED? (Preventive Vision)
                # This returns trains from BOTH directions on this physical track.
                occupants = TrafficManager.get_occupants(edge)
                is_occupied = len(occupants) > 0
                
                if not has_alert and not is_occupied:
                    valid_edge = edge
                    break 
            
            if valid_edge:
                self.current_edge = valid_edge
                self.progress = 0.0
                self.segment_start_time = self.current_time_accumulated
                self.waiting_for_track_fix = False 
                
                TrafficManager.update_train_position(self.current_edge, self.id, self.progress)
                print(f"[TRAIN {self.id}] Entering Segment: {self.node.id}->{self.target.id} (Via {self.current_edge.track_id})")
            else:
                if not self.waiting_for_track_fix:
                    print(f"[TRAIN {self.id}] 🛑 BLOCKED: All tracks to {self.target.id} are BUSY or BROKEN. Waiting.")
                self.waiting_for_track_fix = True
                return
        else:
            self.finished = True
            TrafficManager.remove_train(self.id)
            print(f"[TRAIN {self.id}] FINISHED ROUTE at {self.node.id}")

    def get_state(self, edges):
        s0 = edges[0].edge_type
        s1 = edges[1].edge_type
        return (self.node.id, self.target.id, s0, s1)

    def update(self, dt_minutes):
        if self.finished: return
        
        # --- CRITICAL FIX: PERSISTENCE FOR BROKEN TRAINS ---
        # Even if collided, we must update TrafficManager every frame.
        # Otherwise, after a 'Reset', this train becomes a ghost that others drive through.
        if self.collision_detected:
             TrafficManager.update_train_position(self.current_edge, self.id, self.progress)
             TrafficManager.report_issue(self.node.id, self.target.id, self.current_edge.track_id)
             return
        # ---------------------------------------------------

        self.current_time_accumulated += dt_minutes
        
        # Report Obstacles if we are on them
        if self.current_edge and self.current_edge.edge_type == EdgeType.OBSTACLE:
            if not TrafficManager.check_alert(self.node.id, self.target.id, self.current_edge.track_id):
                TrafficManager.report_issue(self.node.id, self.target.id, self.current_edge.track_id)

        if self.is_in_siding:
            elapsed = self.current_time_accumulated - self.siding_entry_time
            if elapsed >= self.siding_wait_duration:
                self.node.trains_in_siding.remove(self.id)
                self.is_in_siding = False
                self.setup_segment()
            return
        
        # Waiting for track to clear
        if self.waiting_for_track_fix:
            can_go = False
            possible_edges = self.node.neighbors[self.target.id]
            for edge in possible_edges:
                has_alert = TrafficManager.check_alert(self.node.id, self.target.id, edge.track_id)
                occupants = TrafficManager.get_occupants(edge)
                is_occupied = len(occupants) > 0
                
                if not has_alert and not is_occupied:
                    can_go = True
                    break
            
            if can_go:
                print(f"[TRAIN {self.id}] ✅ Track cleared! Resuming journey.")
                self.waiting_for_track_fix = False
                self.setup_segment()
            return

        if self.is_yielding:
            dist_behind = TrafficManager.get_nearest_train_ahead(self.edge_just_finished, 0.99, self.id)
            if dist_behind is None: 
                self.is_yielding = False
                self.setup_segment() 
            return

        # Movement
        scheduled_duration = self.current_edge.expected_minutes
        elapsed_in_segment = self.current_time_accumulated - self.segment_start_time
        time_remaining = scheduled_duration - elapsed_in_segment
        dist_remaining_km = self.current_edge.real_length_km * (1.0 - self.progress)
        
        if dist_remaining_km <= 0: punctuality_speed = 10.0 
        elif time_remaining <= 0: punctuality_speed = self.current_edge.max_speed_kmh
        else: punctuality_speed = dist_remaining_km / (time_remaining / 60.0)

        punctuality_speed = max(punctuality_speed, 20.0)
        punctuality_speed = min(punctuality_speed, self.current_edge.max_speed_kmh)

        dist_ahead = TrafficManager.get_nearest_train_ahead(self.current_edge, self.progress, self.id)
        obstacle_alert = TrafficManager.check_alert(self.node.id, self.target.id, self.current_edge.track_id)
        
        safety_speed = self.current_edge.max_speed_kmh 

        if dist_ahead is not None:
            if dist_ahead < 0.01: 
                self.handle_collision()
                return
            elif dist_ahead < self.SAFE_DISTANCE_PCT: safety_speed = 0.0 
            elif dist_ahead < (self.SAFE_DISTANCE_PCT * 4): safety_speed = 30.0 
        
        if obstacle_alert: safety_speed = 0.0

        target_speed = min(punctuality_speed, safety_speed)

        if self.current_speed_kmh < target_speed:
            self.current_speed_kmh = min(self.current_speed_kmh + self.ACCELERATION * dt_minutes, target_speed)
        elif self.current_speed_kmh > target_speed:
            self.current_speed_kmh = max(self.current_speed_kmh - self.BRAKING * dt_minutes, target_speed)

        length = self.current_edge.real_length_km
        if length <= 0: length = 1.0
        
        distance_km = self.current_speed_kmh * (dt_minutes / 60.0)
        self.progress += distance_km / length

        TrafficManager.update_train_position(self.current_edge, self.id, self.progress)
        
        target_clock = self.schedule.get(self.target.id)
        current_clock = self.start_time + self.current_time_accumulated
        if target_clock: self.delay_global = current_clock - target_clock 
        self.status = TrainStatus.RETARD_MODERAT if abs(self.delay_global) >= 2 else TrainStatus.SENSE_RETARD

        if self.progress >= 1.0:
            self.arrive_at_station()

    def handle_collision(self):
        print(f"[TRAIN {self.id}] COLLISION !!! at {self.node.id}->{self.target.id}")
        self.collision_detected = True
        self.status = TrainStatus.AVARIAT
        self.current_speed_kmh = 0.0
        
        # Report immediately
        TrafficManager.report_issue(self.node.id, self.target.id, self.current_edge.track_id)
        
        reward = -2000.0 
        possible_edges = self.node.neighbors[self.target.id]
        state = self.get_state(possible_edges)
        self.agent.learn(state, self.current_edge.track_id, reward, state)

    def arrive_at_station(self):
        TrafficManager.remove_train(self.id)
        self.edge_just_finished = self.current_edge
        
        target_arrival_time = self.schedule.get(self.target.id)
        actual_arrival_time = self.start_time + self.current_time_accumulated
        abs_delay = abs(actual_arrival_time - target_arrival_time) if target_arrival_time else 0
        
        if abs_delay < 5.0: 
             TrafficManager.clear_issue(self.node.id, self.target.id, self.current_edge.track_id)
        
        reward = 100.0 - (abs_delay * 10.0)
        state = self.get_state(self.node.neighbors[self.target.id])
        self.agent.learn(state, self.current_edge.track_id, reward, state)

        self.node = self.target
        self.route_index += 1
        
        if self.route_index < len(self.route) - 1:
            self.target = self.route[self.route_index + 1]
            
            if self.node.has_siding and len(self.node.trains_in_siding) < 2:
                if self.delay_global < -10.0 or (self.delay_global > 15.0 and self.check_follower_close()):
                    self.enter_siding(wait_time=5.0)
                    return

            if self.delay_global > 5.0 and self.check_follower_close():
                 self.is_yielding = True
                 return 
            
            self.setup_segment()
        else:
            if self.is_in_siding: self.node.trains_in_siding.remove(self.id)
            self.finished = True
            print(f"🏁 [TRAIN {self.id}] ROUTE COMPLETED.")

    def check_follower_close(self):
        return False 

    def enter_siding(self, wait_time):
        self.is_in_siding = True
        self.siding_entry_time = self.current_time_accumulated
        self.siding_wait_duration = wait_time
        self.node.trains_in_siding.append(self.id)

    def draw(self, screen):
        if self.finished: return
        color = (0, 200, 0) 
        if self.is_in_siding: color = (255, 140, 0)
        elif self.is_yielding: color = (0, 0, 255)
        elif self.waiting_for_track_fix: color = (255, 0, 255)
        elif abs(self.delay_global) > 5: color = (230, 140, 0) 
        if self.collision_detected: color = (0, 0, 0) 
        
        start_x, start_y = self.node.x, self.node.y
        if self.is_yielding or self.waiting_for_track_fix or self.is_in_siding:
            pygame.draw.circle(screen, color, (int(start_x), int(start_y)), 8)
            return

        end_x, end_y = self.target.x, self.target.y
        
        off = 5 if self.current_edge.track_id == 0 else -5
        if getattr(self.current_edge, 'reverse_draw', False):
            off = -off
            
        dx = end_x - start_x
        dy = end_y - start_y
        dist = (dx**2 + dy**2)**0.5
        if dist == 0: dist = 1
        perp_x = -dy / dist
        perp_y = dx / dist
        safe_progress = min(1.0, self.progress)
        cur_x = start_x + dx * safe_progress + perp_x * off
        cur_y = start_y + dy * safe_progress + perp_y * off
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)