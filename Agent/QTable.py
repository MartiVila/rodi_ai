from collections import defaultdict
import numpy as np
import random
class QTable:
    def __init__(self, n_actions, alpha=0.7, gamma=0.9,
                 epsilon=0.9, epsilon_decay=0.1, min_epsilon=0.1):
        self.n_actions = n_actions
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.min_epsilon = min_epsilon
        self.q = defaultdict(lambda: np.zeros(n_actions))

    def act(self, state):
        if random.random() < self.epsilon:
            return random.randrange(self.n_actions)
        return int(np.argmax(self.q[state]))

    def learn(self, state, action, reward, next_state, done):
        current_q = self.q[state][action]
        if done:
            target = reward
        else:
            target = reward + self.gamma * np.max(self.q[next_state])
        self.q[state][action] = current_q + self.alpha * (target - current_q)
