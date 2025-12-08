import pygame
import sys
import math
import random
from enum import Enum


class EdgeType(Enum):
    NORMAL = 1
    OBSTACLE = 2

class Node:
    def __init__(self, x, y, node_id):
        self.x = x
        self.y = y
        self.id = node_id
        self.radius = 20

    def draw(self, screen):
        pygame.draw.circle(screen, (0, 100, 200), (self.x, self.y), self.radius)
        font = pygame.font.Font(None, 20)
        text = font.render(str(self.id), True, (255, 255, 255))
        screen.blit(text, (self.x - 8, self.y - 8))
        
        # Draw station name below the node
        if hasattr(self, 'name'):
            name_font = pygame.font.Font(None, 14)
            name_text = name_font.render(self.name, True, (50, 50, 50))
            text_width = name_text.get_width()
            screen.blit(name_text, (self.x - text_width // 2, self.y + 25))

class Edge:
    def __init__(self, node1, node2, edge_type):
        self.node1 = node1
        self.node2 = node2
        self.edge_type = edge_type
        self.speed = 1 if edge_type == EdgeType.NORMAL else 0.5

    def draw(self, screen):
        color = (0, 200, 0) if self.edge_type == EdgeType.NORMAL else (200, 0, 0)
        
        # Offset the edge perpendicular to the line direction
        offset = 10 if self.edge_type == EdgeType.NORMAL else -10
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        length = math.sqrt(dx*dx + dy*dy)
        
        # Perpendicular offset
        offset_x = -dy / length * offset
        offset_y = dx / length * offset
        
        start_pos = (self.node1.x + offset_x, self.node1.y + offset_y)
        end_pos = (self.node2.x + offset_x, self.node2.y + offset_y)
        
        pygame.draw.line(screen, color, start_pos, end_pos, 3)
        
        mid_x = (start_pos[0] + end_pos[0]) / 2
        mid_y = (start_pos[1] + end_pos[1]) / 2
        label = "Normal" if self.edge_type == EdgeType.NORMAL else "Obstacle"
        font = pygame.font.Font(None, 16)
        text = font.render(label, True, color)
        screen.blit(text, (mid_x, mid_y))

class Train:
    def __init__(self, start_node, end_node, edge):
        self.start_node = start_node
        self.end_node = end_node
        self.edge = edge
        self.progress = 0
        self.speed = edge.speed / 100

    def update(self):
        self.progress += self.speed
        if self.progress >= 1:
            self.progress = 1

    def draw(self, screen):
        # Calculate position with offset for the edge
        offset = 10 if self.edge.edge_type == EdgeType.NORMAL else -10
        dx = self.end_node.x - self.start_node.x
        dy = self.end_node.y - self.start_node.y
        length = math.sqrt(dx*dx + dy*dy)
        
        offset_x = -dy / length * offset
        offset_y = dx / length * offset
        
        x = (self.start_node.x + offset_x) + (dx * self.progress)
        y = (self.start_node.y + offset_y) + (dy * self.progress)
        pygame.draw.rect(screen, (255, 200, 0), (x - 10, y - 8, 20, 16))

    def is_finished(self):
        return self.progress >= 1

class Simulator:
    def __init__(self):
        pygame.init()
        self.width, self.height = 1400, 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Train Simulator - R7 Line")
        self.clock = pygame.time.Clock()
        self.running = True
        self.selected_edge = None
        self.train = None
        self.train_path = []  # Path of edges the train will take
        self.current_edge_index = 0  # Current edge in the path
        
        # R7 Station names (short versions for display)
        self.station_names = [
            "Fabra i Puig",
            "Torre Baró",
            "Montcada Bif.",
            "Montcada Man.",
            "Montcada S.M.",
            "Cerdanyola V.",
            "Cerdanyola U."
        ]
        
        # Create 7 nodes for R7 line
        spacing = 200
        start_x = 100
        y_pos = 300
        self.nodes = []
        for i in range(7):
            node = Node(start_x + i * spacing, y_pos, i + 1)
            node.name = self.station_names[i]
            self.nodes.append(node)
        
        # Create edges between consecutive nodes (6 segments total)
        self.all_edges = []
        self.edge_segments = {}
        
        # Randomly assign edge order for each segment
        for i in range(6):
            normal_edge = Edge(self.nodes[i], self.nodes[i + 1], EdgeType.NORMAL)
            obstacle_edge = Edge(self.nodes[i], self.nodes[i + 1], EdgeType.OBSTACLE)
            
            # Randomly decide which edge goes in position 0 and which in position 1
            if random.random() < 0.5:
                self.edge_segments[i] = [normal_edge, obstacle_edge]  # NORMAL at 0, OBSTACLE at 1
            else:
                self.edge_segments[i] = [obstacle_edge, normal_edge]  # OBSTACLE at 0, NORMAL at 1
            
            self.all_edges.extend([normal_edge, obstacle_edge])
        
        # Q-learning related attributes
        self.episode_step = 0
        self.max_steps = 1200
        self.target_time = 600  # Target arrival time for all normal edges (6 segments)
        self.is_training = False
        self.num_segments = 6

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.select_edge(event.pos)

    def select_edge(self, pos):
        """Select an edge to add to the train's path"""
        if not self.is_training:  # Only allow manual selection outside training
            for segment_id, edges in self.edge_segments.items():
                for edge in edges:
                    # Calculate the actual offset position of the edge
                    offset = 10 if edge.edge_type == EdgeType.NORMAL else -10
                    dx = edge.node2.x - edge.node1.x
                    dy = edge.node2.y - edge.node1.y
                    length = math.sqrt(dx*dx + dy*dy)
                    
                    offset_x = -dy / length * offset
                    offset_y = dx / length * offset
                    
                    mid_x = (edge.node1.x + edge.node2.x) / 2 + offset_x
                    mid_y = (edge.node1.y + edge.node2.y) / 2 + offset_y
                    
                    if math.sqrt((pos[0] - mid_x)**2 + (pos[1] - mid_y)**2) < 40:
                        self.train_path.append(edge)
                        if self.train is None:
                            self._start_train()
                        return

    def update(self):
        if self.train and not self.train.is_finished():
            self.train.update()
        elif self.train and self.train.is_finished() and self.current_edge_index < len(self.train_path) - 1:
            # Move to next edge in path
            self.current_edge_index += 1
            current_edge = self.train_path[self.current_edge_index]
            self.train = Train(current_edge.node1, current_edge.node2, current_edge)
        
        if self.is_training:
            self.episode_step += 1
    
    def _start_train(self):
        """Start the train on the first edge of the path"""
        if self.train_path:
            current_edge = self.train_path[0]
            self.train = Train(current_edge.node1, current_edge.node2, current_edge)
            self.current_edge_index = 0

    def draw(self):
        self.screen.fill((240, 240, 240))
        
        # Draw all edges
        for edge in self.all_edges:
            edge.draw(self.screen)
        
        # Draw all nodes
        for node in self.nodes:
            node.draw(self.screen)
        
        # Draw train
        if self.train:
            self.train.draw(self.screen)
        
        # Draw path (for training visualization)
        if self.is_training and self.train_path:
            font = pygame.font.Font(None, 16)
            path_str = " -> ".join([str(self.train_path[0].node1.id)] + [str(e.node2.id) for e in self.train_path])
            text = font.render(f"Path: {path_str}", True, (100, 100, 100))
            self.screen.blit(text, (10, 40))
        
        font = pygame.font.Font(None, 20)
        text = font.render("Click on an edge to build path (or use agent)", True, (0, 0, 0))
        self.screen.blit(text, (10, 10))
        
        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()
        sys.exit()
    
    # Q-Learning API Methods
    def reset(self):
        """Reset the simulator for a new episode"""
        self.train = None
        self.train_path = []
        self.current_edge_index = 0
        self.episode_step = 0
        return self.get_state()
    
    def get_state(self):
        """Return the current state for Q-learning
        State: (current_segment, train_progress, edge_type)
        current_segment: 0-5 (which segment we're on), 6 = destination reached
        """
        if self.train is None:
            segment = 0
            progress = 0
            edge_id = -1
        else:
            segment = self.current_edge_index
            progress = int(self.train.progress * 100)
            edge_id = 0 if self.train.edge.edge_type == EdgeType.NORMAL else 1
        
        return (segment, progress, edge_id)
    
    def step(self, action):
        """Execute one step of the environment
        
        action: 0 = NORMAL edge for current segment, 1 = OBSTACLE edge for current segment
        
        Returns: (state, reward, done, info)
        """
        reward = 0
        
        # If train is idle or finished, make a new action
        if self.train is None or self.train.is_finished():
            if self.current_edge_index < self.num_segments:
                # We can make a decision for the next segment
                segment = self.current_edge_index
                edge = self.edge_segments[segment][action]
                self.train = Train(edge.node1, edge.node2, edge)
                self.train_path.append(edge)
        
        # Update train position (multiple steps until it finishes)
        while self.train and not self.train.is_finished():
            self.train.update()
            if self.is_training:
                self.episode_step += 1
        
        # Give reward when edge is completed
        if self.train and self.train.is_finished():
            # Reward for choosing this edge
            if self.train.edge.edge_type == EdgeType.NORMAL:
                reward = 10.0  # Good choice - faster
            else:
                reward = 2.0   # Slower choice
            
            # Move to next segment
            if self.current_edge_index < self.num_segments:
                self.current_edge_index += 1
            
            # Additional final reward if we completed all segments
            if self.current_edge_index >= self.num_segments:
                time_diff = abs(self.episode_step - self.target_time)
                bonus = max(0, 80 - (time_diff * 0.2))
                reward += bonus
        
        # Check if episode is done
        done = self._is_done()
        
        state = self.get_state()
        info = {
            'train_finished': self.train is not None and self.train.is_finished(),
            'current_segment': self.current_edge_index,
            'edge_type': self.train.edge.edge_type if self.train else None,
            'episode_step': self.episode_step
        }
        
        return state, reward, done, info
    
    def _calculate_reward(self):
        """Calculate reward for the current step"""
        # Rewards are now calculated in step() method
        return 0
    
    def _is_done(self):
        """Check if episode is done"""
        # Episode is done when all segments are complete or max steps exceeded
        return self.current_edge_index >= self.num_segments or self.episode_step >= self.max_steps

if __name__ == "__main__":
    simulator = Simulator()
    simulator.run()