import random
import numpy as np
import pickle  
import os   
import json        
import os
import ast   

class QLearningAgent:
    def __init__(self, learning_rate=0.1, discount_factor=0.9, epsilon=0.1):

        # Hiperparàmetres
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.q_table = {} 

    def get_q_value(self, state, action):
        return self.q_table.get(state, [0.0, 0.0])[action]

    def choose_action(self, state):
        """
        Elecció de vies. Vies hardcodeades a 0 i 1.
        #TODO Fer num_vies dinàmic


        :param state: L'estat actual del tren
        :return: L'acció triada (0 o 1)
        """


        if random.random() < self.epsilon:
            return random.choice([0, 1])
        
        q_values = self.q_table.get(state, [0.0, 0.0])
        if q_values[0] == q_values[1]:
            return random.choice([0, 1])
        return np.argmax(q_values)

    def learn(self, state, action, reward, next_state):
        current_q = self.get_q_value(state, action)
        next_max_q = np.max(self.q_table.get(next_state, [0.0, 0.0]))
        
        new_q = current_q + self.lr * (reward + self.gamma * next_max_q - current_q)
        
        if state not in self.q_table:
            self.q_table[state] = [0.0, 0.0]
        
        self.q_table[state][action] = new_q




    ############################################################################################
    ########################   MÈTODES DE PERSISTÈNCIA   #######################################
    ############################################################################################

    def save_table(self, filename="q_table.json"):
        """
        Guarda la Q-Table en un fitxer .json converting les claus a string.
        Inclou els noms de les accions per millorar la llegibilitat.
        
        :param filename: Nom del fitxer (per defecte .json)
        """
        try:
            # Noms de les accions per fer-ho més llegible
            action_names = ["VIA_0", "VIA_1"]
            
            # JSON requereix claus string. Convertim amb noms d'accions
            serializable_table = {}
            for state, q_values in self.q_table.items():
                # Crear un diccionari amb nom d'acció i valor Q
                actions_dict = {
                    action_names[i]: q_values[i] 
                    for i in range(len(q_values))
                }
                serializable_table[str(state)] = actions_dict
            
            with open(filename, "w", encoding='utf-8') as f:
                json.dump(serializable_table, f, indent=4, ensure_ascii=False)
                
            print(f"[Agent] Q-Table guardada correctament a '{filename}'. Entrades: {len(self.q_table)}")
        except Exception as e:
            print(f"[Error] No s'ha pogut guardar la Q-Table: {e}")

    def load_table(self, filename="q_table.json"):
        """
        Carrega la Q-Table des d'un fitxer .json i reconstrueix els estats.
        Suporta tant el format nou (amb noms d'accions) com l'antic (llista de valors).
        """
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding='utf-8') as f:
                    data = json.load(f)
                
                # Reconstruim les claus originals i els valors Q
                self.q_table = {}
                for state_str, actions in data.items():
                    state_key = ast.literal_eval(state_str)
                    
                    # Si és el format nou (diccionari amb noms d'accions)
                    if isinstance(actions, dict):
                        # Convertir {"VIA_0": val1, "VIA_1": val2} -> [val1, val2]
                        # També suporta format antic amb "ESPERAR"/"AVANÇAR"
                        q_values = [
                            actions.get("VIA_0", actions.get("ESPERAR", 0.0)), 
                            actions.get("VIA_1", actions.get("AVANÇAR", 0.0))
                        ]
                    else:
                        # Format antic (llista directa)
                        q_values = actions
                    
                    self.q_table[state_key] = q_values
                
                print(f"[Agent] Q-Table carregada! Entrades recuperades: {len(self.q_table)}")
            except Exception as e:
                print(f"[Error] Fitxer trobat però corrupta o incompatible: {e}")
        else:
            print(f"[Agent] No s'ha trobat '{filename}'. S'inicia amb Q-Table buida.")


    """
    def save_table(self, filename="q_table.pkl"):
        
        Guarda la Q-Table en un fitxer .pkl
        
        :param filename: Nom del fitxer on es guardarà la Q-Table
        
        try:
            with open(filename, "wb") as f:
                pickle.dump(self.q_table, f)
            print(f"[Agent] Q-Table guardada correctament a '{filename}'. Entrades: {len(self.q_table)}")
        except Exception as e:
            print(f"[Error] No s'ha pogut guardar la Q-Table: {e}")

    def load_table(self, filename="q_table.pkl"):
        Carrega la Q-Table des d'un fitxer .pkl si existeix
        if os.path.exists(filename):
            try:
                with open(filename, "rb") as f:
                    self.q_table = pickle.load(f)
                print(f"[Agent] Q-Table carregada! Entrades recuperades: {len(self.q_table)}")
            except Exception as e:
                print(f"[Error] Fitxer trobat però corrupta o incompatible: {e}")
        else:
            print(f"[Agent] No s'ha trobat '{filename}'. S'inicia amb Q-Table buida.")

    """