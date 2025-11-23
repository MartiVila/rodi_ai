import random
import numpy as np
class Train_Agent:
    def __init__(self, n_states, n_actions,
                 alpha=0.7, gamma=0.9,
                 epsilon=0.9, epsilon_decay=0.1,
                 min_epsilon=0.1):
        self.n_states = n_states
        self.n_actions = n_actions
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.min_epsilon = min_epsilon

        self.q_table = np.zeros((n_states, n_actions))

    def act(self, state):
        # epsilon-greedy
        if random.random() < self.epsilon:
            return random.randrange(self.n_actions)
        return int(np.argmax(self.q_table[state]))

    def learn(self, state, action, reward, next_state, done):
        current_q = self.q_table[state, action]
        if done:
            target = reward
        else:
            target = reward + self.gamma * np.max(self.q_table[next_state])
        self.q_table[state, action] = current_q + self.alpha * (target - current_q)

    def decay_epsilon(self):
        self.epsilon = max(self.min_epsilon, self.epsilon - self.epsilon_decay)
