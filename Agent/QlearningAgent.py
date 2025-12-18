class QLearningAgent:
    def __init__(self, learning_rate=0.1, discount_factor=0.9, epsilon=0.1):
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.q_table = {} # Key: (node_origen, node_desti, estat_via_0, estat_via_1) -> Value: [Q_via0, Q_via1]

    def get_q_value(self, state, action):
        return self.q_table.get(state, [0.0, 0.0])[action]

    def choose_action(self, state):
        """Retorna 0 (Via 1) o 1 (Via 2)"""
        # Epsilon-greedy: Exploració vs Explotació
        if random.random() < self.epsilon:
            return random.choice([0, 1])
        
        q_values = self.q_table.get(state, [0.0, 0.0])
        # Si són iguals, tria a l'atzar, si no, el millor
        if q_values[0] == q_values[1]:
            return random.choice([0, 1])
        return np.argmax(q_values)

    def learn(self, state, action, reward, next_state):
        """Actualitza la Q-Table segons l'equació de Bellman"""
        current_q = self.get_q_value(state, action)
        
        # Max Q del següent estat (si fos una cadena de decisions)
        # En aquest cas simplificat, el següent estat és 'arribat', Q=0, però ho deixem preparat
        next_max_q = np.max(self.q_table.get(next_state, [0.0, 0.0]))
        
        new_q = current_q + self.lr * (reward + self.gamma * next_max_q - current_q)
        
        if state not in self.q_table:
            self.q_table[state] = [0.0, 0.0]
        
        self.q_table[state][action] = new_q