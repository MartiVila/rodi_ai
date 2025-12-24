import time
import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd # Fem servir pandas per la mitjana mòbil eficient
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

# === GRID SEARCH EXTÈS PER A 10.000 DIES ===
# Nota: Els decays són més lents (0.999+) per aprofitar els 10k dies.
HYPERPARAMS_GRID = [
    # Agressiu: Alpha 0.2 (aprèn ràpid), Gamma 0.8 (no mira gaire al futur), Decay lent
    {'alpha': 0.2,  'gamma': 0.99, 'epsilon_decay': 0.999,  'label': 'Agressiu (a=0.2)'},
    
    # Equilibrat
    {'alpha': 0.05, 'gamma': 0.99, 'epsilon_decay': 0.9995, 'label': 'Equilibrat (a=0.05)'},
    
    # Conservador
    {'alpha': 0.01, 'gamma': 0.99, 'epsilon_decay': 0.9999, 'label': 'Estratègic (a=0.01)'}
]

TOTAL_DAYS = 10000        # Simulació de llarga durada
MINUTES_PER_DAY = 1440 
SAVE_INTERVAL = 1000      # Guardem checkpoints cada 1000 dies

def run_experiment(params):
    """Executa un entrenament complet amb un set d'hiperparàmetres"""
    print(f"\n>>> INICIANT EXPERIMENT: {params['label']} <<<")
    
    # Neteja de fitxers previs
    brain_filename = f"q_table_{params['label'].replace(' ', '_').replace('(', '').replace(')', '')}.pkl"
    #brain_filename = f"q_table.pkl"
    brain_path = os.path.join("Agent/Qtables", brain_filename)
    if os.path.exists(brain_path): os.remove(brain_path)

    # Setup
    manager = TrafficManager(width=1000, height=1000, is_training=True)
    manager.brain = QLearningAgent(
        alpha=params['alpha'], 
        gamma=params['gamma'], 
        epsilon=1.0 
    )
    manager.brain.load_table()
    
    history_avg_delay = []
    
    start_time = time.time()

    # --- BUCLE DE DIES ---
    for day in range(1, TOTAL_DAYS + 1):
        # Reset Diari
        manager.active_trains.clear()
        TrafficManager._train_positions.clear()
        manager.completed_train_logs.clear()
        manager.sim_time = 0.0
        manager.last_spawn = -manager.SPAWN_INTERVAL
        manager.reset_network_status()
        
        delays_in_step = []
        
        # Simulació minut a minut
        for _ in range(MINUTES_PER_DAY):
            manager.update(dt_minutes=1.0)
            if manager.active_trains:
                step_delays = [abs(t.calculate_delay()) for t in manager.active_trains]
                delays_in_step.append(np.mean(step_delays))
        
        # Mètriques
        daily_avg = np.mean(delays_in_step) if delays_in_step else 0
        history_avg_delay.append(daily_avg)
        
        # Decay (més lent per a 10k dies)
        manager.brain.decay_epsilon(params['epsilon_decay'], min_epsilon=0.01)
        
        # Logs i Checkpoints
        if day % 100 == 0:
            elapsed = time.time() - start_time
            # Estimació de temps restant
            days_left = TOTAL_DAYS - day
            rate = day / elapsed
            eta_min = (days_left / rate) / 60 if rate > 0 else 0
            
            print(f"   Dia {day:05d} | Eps: {manager.brain.epsilon:.4f} | Retard: {daily_avg:.2f}m | ETA: {eta_min:.1f} min")

        if day % SAVE_INTERVAL == 0:
            manager.brain.save_table(brain_path)

    # Guardat final
    manager.brain.save_table(brain_path)
    return history_avg_delay, manager.completed_train_logs, manager

def save_report(logs, params, history):
    """Genera l'informe detallat amb mètriques d'estabilitat"""
    safe_label = params['label'].replace(' ', '_').replace('(', '').replace(')', '').replace('=', '')
    filename = f"{OUTPUT_DIR}/report_{safe_label}.txt"
    
    # Calculem estabilitat (Desviació estàndard dels últims 1000 dies)
    final_avg = np.mean(history[-1000:])
    stability = np.std(history[-1000:])
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"=== INFORME EXHAUSTIU: {params['label']} ===\n")
        f.write(f"Dies simulats: {TOTAL_DAYS}\n")
        f.write(f"Retard Final (Mitjana últims 1000 dies): {final_avg:.4f} min\n")
        f.write(f"Estabilitat (Std Dev últims 1000 dies): {stability:.4f} min\n")
        f.write(f"Epsilon Final: {params['epsilon_decay']}^{TOTAL_DAYS} ~ 0.01\n\n")
        
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
        
        # PLOT SUAVITZAT (Rolling Average)
        # Amb 10.000 punts, necessitem suavitzar per veure res útil
        data_series = pd.Series(history)
        smooth_data = data_series.rolling(window=200).mean() # Finestra de 200 dies
        
        plt.plot(smooth_data, label=f"{params['label']}", linewidth=2)
        # Opcional: Pintar l'ombra de la variància si es vol, però embruta molt amb tantes línies

    plt.xlabel('Dies (Episodis)')
    plt.ylabel('Retard Promig (Mitjana Mòbil 200 dies)')
    plt.title(f'Convergència a Llarg Termini ({TOTAL_DAYS} dies)')
    plt.legend()
    plt.grid(True, alpha=0.3, which='both')
    plt.minorticks_on()
    
    # Zoom a la zona d'interès (si el retard és baix)
    # plt.ylim(0, 15) 
    
    plot_path = f"{PLOTS_DIR}/exhaustive_comparison.png"
    plt.savefig(plot_path, dpi=300) # Alta resolució
    print(f"\n[GRÀFIC FINAL] Guardat a: {plot_path}")
    
    print("\n=== EXPERIMENT FINALITZAT ===")

if __name__ == "__main__":
    main()