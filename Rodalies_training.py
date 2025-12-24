import time
import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict

# Imports del teu entorn
from Enviroment.TrafficManager import TrafficManager
from Enviroment.Train import Train
from Enviroment.Datas import Datas
from Agent.QlearningAgent import QLearningAgent

# === CONFIGURACIÓ DE L'EXPERIMENT ===
OUTPUT_DIR = "Enviroment/informe_exhaustiu"
PLOTS_DIR = "Agent/Plots_Exhaustius"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)

# === GRID SEARCH ===
HYPERPARAMS_GRID = [
     {'alpha': 0.2,  'gamma': 0.99, 'epsilon_decay': 0.999,  'label': 'Agressiu (a=0.2)'},
    {'alpha': 0.05, 'gamma': 0.99, 'epsilon_decay': 0.9995, 'label': 'Equilibrat (a=0.05)'},
     {'alpha': 0.01, 'gamma': 0.99, 'epsilon_decay': 0.9999, 'label': 'Estratègic (a=0.01)'}
]

TOTAL_DAYS = 1000       
MINUTES_PER_DAY = 1440 
SAVE_INTERVAL = 1000      

def setup_curriculum(manager):
    """
    Defineix els nivells de dificultat tallant la llista d'estacions.
    Retorna les claus dels nivells en ordre de dificultat.
    """
    full_route = manager.lines['R1_NORD'] # La llista completa de noms
    
    # Creem noves entrades al diccionari de línies del manager
    manager.lines['NIVELL_1'] = full_route[:5]   # Fàcil: 5 Estacions (fins Clot/St Adria)
    manager.lines['NIVELL_2'] = full_route[:10]  # Mig: 10 Estacions (fins Montgat)
    manager.lines['NIVELL_3'] = full_route[:15]  # Difícil: 15 Estacions (fins Mataró)
    manager.lines['NIVELL_4'] = full_route       # Complet: Tota la línia
    
    print("[Curriculum] Nivells generats: NIVELL_1 (5), NIVELL_2 (10), NIVELL_3 (15), NIVELL_4 (Totes)")
    return ['NIVELL_1', 'NIVELL_2', 'NIVELL_3', 'NIVELL_4']

def run_experiment(params):
    print(f"\n>>> INICIANT EXPERIMENT: {params['label']} <<<")
    
    brain_filename = f"q_table_{params['label'].replace(' ', '_').replace('(', '').replace(')', '')}.pkl"
    brain_path = os.path.join("Agent/Qtables", brain_filename)
    #if os.path.exists(brain_path): os.remove(brain_path)

    # 1. Inicialitzem el Manager
    manager = TrafficManager(width=1000, height=1000, is_training=True)
    
    # 2. Configurem el Cervell (Agent)
    manager.brain = QLearningAgent(
        alpha=params['alpha'], 
        gamma=params['gamma'], 
        epsilon=1.0 # Comencem explorant al màxim
    )

    manager.brain.load_table(filename=brain_path)
    
    # 3. Configurem el Curriculum
    curriculum_levels = setup_curriculum(manager)
    days_per_level = TOTAL_DAYS // len(curriculum_levels)
    
    history_avg_delay = []
    start_time = time.time()
    
    current_level_idx = 0

    # --- BUCLE DE DIES ---
    for day in range(1, TOTAL_DAYS + 1):
        # A. GESTIÓ DEL CURRICULUM
        # Calculem quin nivell toca segons el dia actual
        new_level_idx = min((day - 1) // days_per_level, len(curriculum_levels) - 1)
        
        # Si canviem de nivell, ho notifiquem i actualitzem el manager
        if new_level_idx != current_level_idx or day == 1:
            current_level_idx = new_level_idx
            level_name = curriculum_levels[current_level_idx]
            manager.current_spawn_line = level_name # [IMPORTANT] Canviem la línia que spawneja
            print(f"\n*** [Dia {day}] CURRICULUM LEVEL UP! -> {level_name} ***")
            
            # Opcional: Podríem pujar una mica l'epsilon aquí si volguéssim re-explorar,
            # però com que l'estat és relatiu (distància/velocitat), l'agent hauria de generalitzar bé.

        # B. RESET DIARI
        manager.active_trains.clear()
        # Accedim a la variable privada/protegida de forma segura o neta si calgués, 
        # però per training ràpid ho fem així segons el teu codi original:
        TrafficManager._train_positions.clear() 
        manager.completed_train_logs.clear()
        manager.sim_time = 0.0
        manager.last_spawn = -manager.SPAWN_INTERVAL
        manager.reset_network_status()
        
        delays_in_step = []
        
        # C. SIMULACIÓ MINUT A MINUT
        for _ in range(MINUTES_PER_DAY):
            manager.update(dt_minutes=1.0)
            
            # Recollim mètriques
            if manager.active_trains:
                # Delay absolut per veure desviació
                step_delays = [abs(t.calculate_delay()) for t in manager.active_trains]
                delays_in_step.append(np.mean(step_delays))
        
        # D. MÈTRIQUES DEL DIA
        daily_avg = np.mean(delays_in_step) if delays_in_step else 0
        history_avg_delay.append(daily_avg)
        
        # E. DECAY DE L'EPSILON
        manager.brain.decay_epsilon(params['epsilon_decay'], min_epsilon=0.01)
        
        # F. LOGS I GUARDAT
        if day % 100 == 0:
            elapsed = time.time() - start_time
            days_left = TOTAL_DAYS - day
            rate = day / elapsed if elapsed > 0 else 0
            eta_min = (days_left / rate) / 60 if rate > 0 else 0
            
            level_name = curriculum_levels[current_level_idx]
            print(f"   Dia {day:05d} [{level_name}] | Eps: {manager.brain.epsilon:.4f} | Retard: {daily_avg:.2f}m | ETA: {eta_min:.1f} min")

        if day % SAVE_INTERVAL == 0:
            manager.brain.save_table(brain_path)

    # Guardat final
    manager.brain.save_table(brain_path)
    return history_avg_delay, manager.completed_train_logs, manager

def save_report(logs, params, history):
    safe_label = params['label'].replace(' ', '_').replace('(', '').replace(')', '').replace('=', '')
    filename = f"{OUTPUT_DIR}/report_{safe_label}.txt"
    
    final_avg = np.mean(history[-1000:])
    stability = np.std(history[-1000:])
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"=== INFORME EXHAUSTIU: {params['label']} ===\n")
        f.write(f"Dies simulats: {TOTAL_DAYS}\n")
        f.write(f"Retard Final (Mitjana últims 1000 dies): {final_avg:.4f} min\n")
        f.write(f"Estabilitat (Std Dev): {stability:.4f} min\n")
        f.write(f"Epsilon Final: ~{params['epsilon_decay']}^{TOTAL_DAYS}\n\n")
        
        if logs:
            f.write(f"--- MOSTRA DE L'ÚLTIM TREN (Dia {TOTAL_DAYS}) ---\n")
            last_train = logs[-1]
            schedule = sorted(last_train['schedule'].items(), key=lambda x: x[1])
            actuals = last_train['actuals']
            route_map = last_train['route_map']
            
            f.write(f"{'ESTACIÓ':<30} | {'PREVIST':<8} | {'REAL':<8} | {'DIF'}\n")
            f.write("-" * 65 + "\n")
            for nid, exp in schedule:
                name = route_map.get(nid, "?")
                act = actuals.get(name)
                if act:
                    diff = act - exp
                    f.write(f"{name:<30} | {int(exp):04d}     | {int(act):04d}     | {diff:+.1f}m\n")
                else:
                    f.write(f"{name:<30} | {int(exp):04d}     | ----     | N/A\n")
    print(f"[Informe] Guardat: {filename}")

def main():
    print(f"=== INICIANT GRID SEARCH EXHAUSTIU ({TOTAL_DAYS} dies) ===")
    results = {}
    plt.figure(figsize=(15, 10))
    
    for params in HYPERPARAMS_GRID:
        history, logs, _ = run_experiment(params)
        results[params['label']] = history
        save_report(logs, params, history)
        
        data_series = pd.Series(history)
        smooth_data = data_series.rolling(window=200).mean()
        plt.plot(smooth_data, label=f"{params['label']}", linewidth=2)

    plt.xlabel('Dies (Episodis)')
    plt.ylabel('Retard Promig (Mitjana Mòbil 200 dies)')
    plt.title(f'Entrenament amb Curriculum ({TOTAL_DAYS} dies)')
    
    # Afegim línies verticals per marcar els canvis de nivell al gràfic
    if 'NIVELL_1' in results: # Si hem corregut alguna cosa
        levels_count = 4 # Sabem que són 4 nivells
        days_per_level = TOTAL_DAYS / levels_count
        for i in range(1, levels_count):
            plt.axvline(x=i*days_per_level, color='k', linestyle='--', alpha=0.3, label='Canvi Nivell' if i==1 else "")

    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plot_path = f"{PLOTS_DIR}/curriculum_comparison.png"
    plt.savefig(plot_path, dpi=300)
    print(f"\n[GRÀFIC FINAL] Guardat a: {plot_path}")
    print("\n=== EXPERIMENT FINALITZAT ===")

if __name__ == "__main__":
    main()