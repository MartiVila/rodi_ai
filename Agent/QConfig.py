class QConfig:
    alpha: float = 0.7      # learning rate
    gamma: float = 0.9      # discount factor
    epsilon: float = 0.9    # exploration rate
    epsilon_decay: float = 0.1
    min_epsilon: float = 0.1
