import random
import numpy as np
import pickle  
import os      
import json
from collections import defaultdict
from Enviroment.Datas import Datas

class QLearningAgent:
    def __init__(self, alpha=0.05, gamma=0.95, epsilon=0.1):
        self.q = defaultdict(float)
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon

    def decay_epsilon(self, decay_rate=0.99, min_epsilon=0.01):
        """
        Redueix epsilon multiplicant-lo pel decay_rate, fins a un mínim.
        Amb aquesta funció permetem que l'agent sigui més conservador a mesur que va avanaçant el temps.
        """
        self.epsilon = max(min_epsilon, self.epsilon * decay_rate)
        
    def discretize_diff(self, diff):
        #Discretitzem la diferència de temps en 5 estats
        if diff < -1:
            return -2  #molt avançat
        elif diff == -1:
            return -1  #lleugermaent avançat
        elif diff == 0:
            return 0   #puntual
        elif diff == 1:
            return 1   #lleugerament retardat
        else:  # diff > 1
            return 2   #molt retardat

    def get_segment_id(self, origin, destination):
        """
        genera un id unic per a cada tram de via, és a dir cada secció entre dues estacions
        """
        return f"{origin}->{destination}"
    
    def action(self, state):
        """state = (origen, destí, diff_discretized, is_blocked)"""
        # Exploració (Epsilon-greedy)
        if random.random() < self.epsilon:
            return random.choice(list(Datas.AGENT_ACTIONS.keys()))
            
        # Explotació: Busquem el valor màxim a la Q-Table
        # Com que self.q és un defaultdict, si l'estat no existeix retornarà 0.0 sense donar error
        qs = [self.q[(state, a)] for a in Datas.AGENT_ACTIONS]
        
        # Si tots són 0 (estat nou), triem a l'atzar per evitar biaix de sempre triar la primera acció (0)
        if all(v == 0 for v in qs):
             return random.choice(list(Datas.AGENT_ACTIONS.keys()))
             
        # Retornem l'índex de l'acció amb més valor Q
        # Utilitzem np.argmax o un mètode robust per llistes
        max_val = max(qs)
        # Si hi ha empat, triem a l'atzar entre els millors
        best_actions = [i for i, val in enumerate(qs) if val == max_val]
        return random.choice(best_actions)

    def update(self, s, a, r, s2):
        if s2 is None:
            # Estat terminal
            self.q[(s, a)] += self.alpha * (r - self.q[(s, a)])
        else:
            max_q_next = max(self.q[(s2, a2)] for a2 in Datas.AGENT_ACTIONS)
            self.q[(s, a)] += self.alpha * (r + self.gamma * max_q_next - self.q[(s, a)])

    ############################################################################################
    ########################   MÈTODES DE PERSISTÈNCIA   #######################################
    ############################################################################################

    def save_table(self, filename="Agent/Qtables/q_table.pkl"):
        """
        Guarda la Q-Table en un fitxer .pkl
        
        :param filename: Nom del fitxer on es guardarà la Q-Table
        """
        try:
            # Assegurem que el directori existeix
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Convertim a dict normal per guardar (pickle de vegades es queixa amb lambdas de defaultdict)
            with open(filename, "wb") as f:
                pickle.dump(dict(self.q), f)
            print(f"[Agent] Q-Table guardada correctament a '{filename}'. Entrades: {len(self.q)}")
        except Exception as e:
            print(f"[Error] No s'ha pogut guardar la Q-Table: {e}")

    def load_table(self, filename="Agent/Qtables/q_table.pkl"):
        """Carrega la Q-Table des d'un fitxer .pkl si existeix"""
        if os.path.exists(filename):
            try:
                with open(filename, "rb") as f:
                    loaded_data = pickle.load(f)
                    # [CORRECCIÓ CLAU] Convertim el dict carregat de nou a defaultdict(float)
                    self.q = defaultdict(float, loaded_data)
                    
                print(f"[Agent] Q-Table carregada! Entrades recuperades: {len(self.q)}")
            except Exception as e:
                print(f"[Error] Fitxer trobat però corrupte o incompatible: {e}")
                # Si falla, ens assegurem que self.q sigui un defaultdict buit i no quedi en estat inconsistent
                self.q = defaultdict(float)
        else:
            print(f"[Agent] No s'ha trobat '{filename}'. S'inicia amb Q-Table buida.")
            self.q = defaultdict(float)

    def export_qtable_to_json(self, filename="Agent/Qtables/q_table.json"):
        """
        Exporta la Q-Table a format JSON per a anàlisi i visualització.
        
        Les claus (state, action) es converteixen a strings per compatibilitat JSON.
        
        :param filename: Nom del fitxer JSON on es guardarà la Q-Table
        """
        try:
            # Assegurem que el directori existeix
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Convertim la Q-Table a un format JSON-serializable
            # Les claus são tuples (state, action), les convertim a strings
            json_data = {
                "metadata": {
                    "total_entries": len(self.q),
                    "learned_entries": len([v for v in self.q.values() if v != 0]),
                    "alpha": self.alpha,
                    "gamma": self.gamma,
                    "epsilon": self.epsilon
                },
                "q_table": {}
            }
            
            # Convertim cada entrada de la Q-Table
            for (state, action), value in self.q.items():
                # Convertim la clau tupla a string per compatibilitat JSON
                key = f"{state}|{action}"
                json_data["q_table"][key] = float(value)
            
            # Guardem a JSON
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            print(f"[Agent] Q-Table exportada a JSON correctament a '{filename}'. "
                f"Entrades: {len(self.q)}")
        except Exception as e:
            print(f"[Error] No s'ha pogut exportar la Q-Table a JSON: {e}")

    #------------------------------------DEBUG-------------------------------------------

    def debug_qtable_stats(self):
        """Estadístiques bàsiques de la memòria de l'agent"""
        total_entrades = len(self.q)
        no_nuls = len([v for v in self.q.values() if v != 0])
        
        print(f"[Agent Stats] Entrades Totals: {total_entrades}")
        print(f"[Agent Stats] Entrades Apreses (!=0): {no_nuls}")
        
        if total_entrades > 0:
            avg_val = sum(self.q.values()) / total_entrades
            print(f"[Agent Stats] Valor mitjà Q: {avg_val:.4f}")