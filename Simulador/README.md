# Train Simulator with Q-Learning

This simulator provides a simple environment for training a Q-learning agent to optimize train arrival times.

## Overview

The simulator consists of two parallel train routes:
- **NORMAL edge**: Fast route (speed = 1.0), green color
- **OBSTACLE edge**: Slow route (speed = 0.5), red color

The goal is to train an agent to choose the optimal route based on the current state to minimize arrival time.

## Simulator API

### State Space
The state is represented as a tuple: `(train_progress, edge_type, episode_step)`
- **train_progress**: Current train position progress (0-100)
- **edge_type**: 0 = NORMAL, 1 = OBSTACLE, -1 = no train active
- **episode_step**: Current step in the episode (0-300)

### Action Space
- **Action 0**: Send train on NORMAL edge
- **Action 1**: Send train on OBSTACLE edge

### Methods

#### `reset()`
Resets the simulator for a new training episode.
```python
state = simulator.reset()
```

#### `step(action)`
Executes one step of the environment with the given action.
```python
state, reward, done, info = simulator.step(action)
```
- **state**: New state after action
- **reward**: Reward for this step
- **done**: Boolean indicating if episode is finished
- **info**: Dictionary with additional information

#### `get_state()`
Returns the current state without modifying the environment.
```python
state = simulator.get_state()
```

### Reward System

Rewards are calculated based on arrival time:
- **NORMAL edge**: Rewards based on proximity to target time (100 steps)
  - Maximum reward: ~100 if arriving at exactly 100 steps
  - Decreases with deviation from target
- **OBSTACLE edge**: Slower route with different target (200 steps)
  - Lower base reward (~50) due to being suboptimal for most cases

## Example Q-Learning Implementation

Here's a complete example of a Q-learning agent:

```python
import numpy as np
from simulator import Simulator, EdgeType
import pickle
import os

class QLearningAgent:
    def __init__(self, learning_rate=0.1, discount_factor=0.95, epsilon=1.0, epsilon_decay=0.995):
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = 0.01
        
        # Q-table: dictionary to handle continuous state space
        self.q_table = {}
        
    def discretize_state(self, state):
        """Convert continuous state to discrete for Q-table indexing"""
        progress, edge_type, step = state
        # Discretize progress into buckets
        progress_bucket = min(progress // 10, 9)  # 0-9
        return (progress_bucket, edge_type, min(step // 30, 9))  # 0-9
    
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
        
        while True:
            action = self.choose_action(state)
            next_state, reward, done, info = simulator.step(action)
            
            # Q-learning update
            current_q = self.get_q_value(state, action)
            next_max_q = max(
                self.get_q_value(next_state, 0),
                self.get_q_value(next_state, 1)
            )
            new_q = current_q + self.lr * (reward + self.gamma * next_max_q - current_q)
            self.set_q_value(state, action, new_q)
            
            total_reward += reward
            state = next_state
            
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
        
        while True:
            # Use greedy policy (no exploration)
            q0 = self.get_q_value(state, 0)
            q1 = self.get_q_value(state, 1)
            action = 0 if q0 >= q1 else 1
            
            next_state, reward, done, info = simulator.step(action)
            total_reward += reward
            
            episode_info.append({
                'state': state,
                'action': action,
                'reward': reward,
                'edge': 'NORMAL' if action == 0 else 'OBSTACLE'
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
    agent = QLearningAgent(learning_rate=0.1, discount_factor=0.95, epsilon=1.0)
    
    # Train the agent
    print("Starting Q-Learning training...")
    rewards = agent.train(simulator, episodes=100)
    
    # Save the trained agent
    agent.save("trained_agent.pkl")
    print("\nAgent saved to trained_agent.pkl")
    
    # Test the trained agent
    print("\nTesting trained agent...")
    test_reward, test_info = agent.test_episode(simulator)
    print(f"Test Episode Reward: {test_reward:.2f}")
    print(f"Agent chose: {test_info[0]['edge']} edge")
```

## Running the Example

1. Save the Q-learning code above as `qlearning.py` in the `Simulador/` directory
2. Run the training:
   ```bash
   python qlearning.py
   ```

3. The agent will:
   - Train for 100 episodes
   - Save the learned Q-table to `trained_agent.pkl`
   - Test on one episode and report the reward

## Customization

You can adjust:
- **Learning rate**: Higher = faster learning but less stable
- **Discount factor**: Higher = values future rewards more
- **Epsilon decay**: How fast exploration decreases
- **Episodes**: Number of training episodes
- **Target time**: Modify `simulator.target_time` to change optimization goal

## Tips for Training

1. Start with high epsilon (1.0) for exploration
2. Use epsilon decay to gradually shift to exploitation
3. Monitor average rewards to check convergence
4. Increase episodes if the agent isn't converging
5. Adjust learning rate if learning is too slow or unstable
