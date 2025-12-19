import random
import numpy as np
import pickle  # [Nova importació] Per serialitzar dades
import os      # [Nova importació] Per comprovar si el fitxer existeix

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
        if random.random() < self.epsilon:
            return random.choice([0, 1])
        
        q_values = self.q_table.get(state, [0.0, 0.0])
        if q_values[0] == q_values[1]:
            return random.choice([0, 1])
        return np.argmax(q_values)

    def learn(self, state, action, reward, next_state):
        """Actualitza la Q-Table segons l'equació de Bellman"""
        current_q = self.get_q_value(state, action)
        next_max_q = np.max(self.q_table.get(next_state, [0.0, 0.0]))
        
        new_q = current_q + self.lr * (reward + self.gamma * next_max_q - current_q)
        
        if state not in self.q_table:
            self.q_table[state] = [0.0, 0.0]
        
        self.q_table[state][action] = new_q

    # --- NOUS MÈTODES DE PERSISTÈNCIA ---

    def save_table(self, filename="q_table.pkl"):
        """Guarda la Q-Table en un fitxer .pkl"""
        try:
            with open(filename, "wb") as f:
                pickle.dump(self.q_table, f)
            print(f"[Agent] Q-Table guardada correctament a '{filename}'. Entrades: {len(self.q_table)}")
        except Exception as e:
            print(f"[Error] No s'ha pogut guardar la Q-Table: {e}")

    def load_table(self, filename="q_table.pkl"):
        """Carrega la Q-Table des d'un fitxer .pkl si existeix"""
        if os.path.exists(filename):
            try:
                with open(filename, "rb") as f:
                    self.q_table = pickle.load(f)
                print(f"[Agent] Q-Table carregada! Entrades recuperades: {len(self.q_table)}")
            except Exception as e:
                print(f"[Error] Fitxer trobat però corrupta o incompatible: {e}")
        else:
            print(f"[Agent] No s'ha trobat '{filename}'. S'inicia amb Q-Table buida.")