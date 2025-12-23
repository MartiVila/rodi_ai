
import random
import numpy as np
import pickle  
import os      
from collections import defaultdict
from Enviroment.Datas import Datas

class QLearningAgent:
    def __init__(self, alpha=0.05, gamma=0.95, epsilon=0.1):
        self.q = defaultdict(float)
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon

    def discretize_diff(self, diff):
        # Discretización fina para distinguir pequeñas desviaciones
        if diff < -1:
            return -2  # Muy adelantado
        elif diff == -1:
            return -1  # Ligeramente adelantado
        elif diff == 0:
            return 0   # Perfecto (a tiempo)
        elif diff == 1:
            return 1   # Ligeramente retrasado
        else:  # diff > 1
            return 2   # Muy retrasado

    def action(self, state):
        """state = (origen, destino, diff_discretized, is_blocked)"""
        if random.random() < self.epsilon:
            return random.choice(list(Datas.AGENT_ACTIONS.keys()))
        qs = [self.q[(state, a)] for a in Datas.AGENT_ACTIONS]
        return qs.index(max(qs))

    def update(self, s, a, r, s2):
        if s2 is None:
            # Estado terminal
            self.q[(s, a)] += self.alpha * (r - self.q[(s, a)])
        else:
            max_q_next = max(self.q[(s2, a2)] for a2 in Datas.AGENT_ACTIONS)
            self.q[(s, a)] += self.alpha * (r + self.gamma * max_q_next - self.q[(s, a)])




    ############################################################################################
    ########################   MÈTODES DE PERSISTÈNCIA   #######################################
    ############################################################################################

    def save_table(self, filename="q_table.pkl"):
        """
        Guarda la Q-Table en un fitxer .pkl
        
        :param filename: Nom del fitxer on es guardarà la Q-Table
        """
        try:
            with open(filename, "wb") as f:
                pickle.dump(self.q, f)
            print(f"[Agent] Q-Table guardada correctament a '{filename}'. Entrades: {len(self.q)}")
        except Exception as e:
            print(f"[Error] No s'ha pogut guardar la Q-Table: {e}")

    def load_table(self, filename="q_table.pkl"):
        """Carrega la Q-Table des d'un fitxer .pkl si existeix"""
        if os.path.exists(filename):
            try:
                with open(filename, "rb") as f:
                    self.q = pickle.load(f)
                print(f"[Agent] Q-Table carregada! Entrades recuperades: {len(self.q)}")
            except Exception as e:
                print(f"[Error] Fitxer trobat però corrupta o incompatible: {e}")
        else:
            print(f"[Agent] No s'ha trobat '{filename}'. S'inicia amb Q-Table buida.")