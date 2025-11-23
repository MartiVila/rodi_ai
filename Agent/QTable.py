import numpy as np

class QTable:

    def __init__(self, n_states: int, n_actions: int):
        self.n_states = n_states
        self.n_actions = n_actions
        self.values = np.zeros((n_states, n_actions))

    def get(self, state: int, action: int) -> float:
        return float(self.values[state, action])

    def get_row(self, state: int) -> np.ndarray:
        return self.values[state]

    def update(self,
               state: int,
               action: int,
               reward: float,
               next_state: int,
               done: bool,
               alpha: float,
               gamma: float) -> None:
        """
        Standard Q-learning update:
        Q(s,a) ← Q(s,a) + α [ r + γ max_a' Q(s',a') − Q(s,a) ]
        """
        current_q = self.values[state, action]
        if done:
            target = reward
        else:
            target = reward + gamma * np.max(self.values[next_state])
        self.values[state, action] = current_q + alpha * (target - current_q)
