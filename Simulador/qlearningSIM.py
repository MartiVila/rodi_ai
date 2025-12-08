import numpy as np
from simulator import Simulator, EdgeType
import pickle
import os

class QLearningAgent:
    def __init__(self, learning_rate=0.2, discount_factor=0.9, epsilon=1.0, epsilon_decay=0.995):
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = 0.05
        
        # Q-table: dictionary to handle continuous state space
        self.q_table = {}
        
    def discretize_state(self, state):
        """Convert continuous state to discrete for Q-table indexing"""
        segment, progress, edge_type = state
        # We only need segment as state since we decide per segment
        # Progress and edge_type are just for info
        return (segment, edge_type)
    
    def get_q_value(self, state, action):
        """Get Q-value for state-action pair"""
        d_state = self.discretize_state(state)
        key = (d_state, action)
        return self.q_table.get(key, 0.0)
    
    def set_q_value(self, state, action, value):
        """Set Q-value for state-action pair"""
        d_state = self.discretize_state(state)
        key = (d_state, action)
        self.q_table[key] = value
    
    def choose_action(self, state):
        """Epsilon-greedy action selection"""
        if np.random.random() < self.epsilon:
            return np.random.choice([0, 1])  # Random action
        else:
            q0 = self.get_q_value(state, 0)
            q1 = self.get_q_value(state, 1)
            return 0 if q0 >= q1 else 1  # Greedy action
    
    def train_episode(self, simulator):
        """Train for one episode"""
        state = simulator.reset()
        total_reward = 0
        decisions = 0
        
        # Make 6 decisions (one per segment in R7 line)
        while decisions < 6:
            action = self.choose_action(state)
            next_state, reward, done, info = simulator.step(action)
            
            total_reward += reward
            
            # Q-learning update
            current_q = self.get_q_value(state, action)
            next_max_q = max(
                self.get_q_value(next_state, 0),
                self.get_q_value(next_state, 1)
            )
            new_q = current_q + self.lr * (reward + self.gamma * next_max_q - current_q)
            self.set_q_value(state, action, new_q)
            
            state = next_state
            decisions += 1
            
            if done:
                break
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        return total_reward
    
    def train(self, simulator, episodes=100):
        """Train the agent for multiple episodes"""
        rewards_history = []
        
        for episode in range(episodes):
            reward = self.train_episode(simulator)
            rewards_history.append(reward)
            
            if (episode + 1) % 10 == 0:
                avg_reward = np.mean(rewards_history[-10:])
                print(f"Episode {episode + 1}/{episodes}, Avg Reward: {avg_reward:.2f}, Epsilon: {self.epsilon:.4f}")
        
        return rewards_history
    
    def save(self, filepath):
        """Save Q-table to file"""
        with open(filepath, 'wb') as f:
            pickle.dump(self.q_table, f)
    
    def load(self, filepath):
        """Load Q-table from file"""
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                self.q_table = pickle.load(f)
    
    def test_episode(self, simulator, render=False):
        """Test the trained agent without exploration"""
        state = simulator.reset()
        total_reward = 0
        episode_info = []
        
        # Make 6 decisions (one per segment in R7 line)
        for decision in range(6):
            # Use greedy policy (no exploration)
            q0 = self.get_q_value(state, 0)
            q1 = self.get_q_value(state, 1)
            action = 0 if q0 >= q1 else 1
            
            # Get the actual edge type at this position
            segment, progress, edge_type = state
            actual_edge = simulator.edge_segments[segment][action]
            
            next_state, reward, done, info = simulator.step(action)
            total_reward += reward
            
            episode_info.append({
                'state': state,
                'action': action,
                'reward': reward,
                'edge': 'NORMAL' if actual_edge.edge_type == EdgeType.NORMAL else 'OBSTACLE',
                'segment': segment,
                'q_values': (q0, q1)
            })
            
            state = next_state
            
            if done:
                break
        
        return total_reward, episode_info


# Main training script
if __name__ == "__main__":
    # Create simulator and agent
    simulator = Simulator()
    simulator.is_training = True
    
    # Print the random configuration for this training session
    print("Starting Q-Learning training on R7 line...")
    print("R7 Line: 7 stations, 6 segments")
    print("Stations: Fabra i Puig -> Torre Baró -> Montcada Bif. -> Montcada Man. -> Montcada S.M. -> Cerdanyola V. -> Cerdanyola U.")
    print("\nEdge configuration for this training session:")
    for seg_id, edges in simulator.edge_segments.items():
        edge0_type = "NORMAL" if edges[0].edge_type == EdgeType.NORMAL else "OBSTACLE"
        edge1_type = "NORMAL" if edges[1].edge_type == EdgeType.NORMAL else "OBSTACLE"
        print(f"  Segment {seg_id}: Action 0 = {edge0_type}, Action 1 = {edge1_type}")
    print("\nReward structure: NORMAL edge = 10 points, OBSTACLE edge = 2 points")
    print("Target time for all NORMAL edges: 600 steps")
    print("Final bonus: up to 80 points for reaching target time\n")
    
    agent = QLearningAgent(learning_rate=0.2, discount_factor=0.9, epsilon=1.0)
    rewards = agent.train(simulator, episodes=500)
    
    # Save the trained agent
    agent.save("trained_agent_r7.pkl")
    print("\nAgent saved to trained_agent_r7.pkl")
    
    # Test the trained agent
    print("\nTesting trained agent...")
    test_reward, test_info = agent.test_episode(simulator)
    print(f"Test Episode Total Reward: {test_reward:.2f}")
    print(f"Test Episode Steps: {simulator.episode_step}")
    print("\nPath taken:")
    station_names = simulator.station_names
    for info in test_info:
        seg = info['segment']
        if seg < len(station_names) - 1:
            print(f"  Segment {seg} ({station_names[seg]} -> {station_names[seg+1]}): "
                  f"Action={info['action']}, Edge={info['edge']}, Reward: {info['reward']:.2f}, Q-values: ({info['q_values'][0]:.2f}, {info['q_values'][1]:.2f})")