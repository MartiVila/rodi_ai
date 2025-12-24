import time
import os
import numpy as np
import matplotlib.pyplot as plt

from Enviroment.TrafficManager import TrafficManager
from Enviroment.Train import Train 

def train_agent():
    print("=== INICIANT ENTRENAMENT HEADLESS (AMB RESET DIARI) ===")
    
    # [CORRECCIÓ FÍSICA]
    print(f"   [FÍSICA] Corregint acceleració: {Train.ACCELERATION} -> 80.0")
    Train.ACCELERATION = 80.0 
    
    TOTAL_DAYS = 300          
    MINUTES_PER_DAY = 1440    
    
    EPSILON_DECAY = 0.98      
    MIN_EPSILON = 0.01        
    
    history_avg_delay = []      
    history_epsilon = []
    
    manager = TrafficManager(width=1000, height=1000)
    manager.reset_network_status()

    start_real_time = time.time()

    for day in range(1, TOTAL_DAYS + 1):
        
        # === NOVETAT: RESET DIARI DE TRENS ===
        # Eliminem tots els trens per començar el dia net
        manager.active_trains.clear()
        
        # IMPORTANITSSIM: Netegem també el registre de posicions estàtic
        # o els trens nous xocaran amb trens "invisibles" del dia anterior.
        TrafficManager._train_positions.clear()
        
        # Reiniciem timers de spawn per no esperar massa al primer tren
        manager.last_spawn = -999 
        # =====================================

        delays_in_step = []
        
        for _ in range(MINUTES_PER_DAY):
            manager.update(dt_minutes=1.0)
            
            if manager.active_trains:
                step_delays = [abs(t.calculate_delay()) for t in manager.active_trains]
                avg_step = np.mean(step_delays)
                delays_in_step.append(avg_step)
        
        # Si no hi ha hagut trens (per error), posem 0
        daily_avg = np.mean(delays_in_step) if delays_in_step else 0
        
        history_avg_delay.append(daily_avg)
        history_epsilon.append(manager.brain.epsilon)

        manager.brain.decay_epsilon(EPSILON_DECAY, MIN_EPSILON)
        
        if day % 10 == 0 or day == 1:
            print(f"Dia {day:03d}/{TOTAL_DAYS} | Eps: {manager.brain.epsilon:.4f} | Retard: {daily_avg:.2f} m | Trens: {len(manager.active_trains)} (Reset fets)")
            manager.save_brain()

    total_time = time.time() - start_real_time
    print(f"\n=== ENTRENAMENT FINALITZAT EN {total_time:.2f} s ===")
    
    manager.save_brain()
    save_convergence_plot(history_avg_delay, history_epsilon)

def save_convergence_plot(delays, epsilons):
    save_dir = "Agent/Plots"
    os.makedirs(save_dir, exist_ok=True)
    
    fig, ax1 = plt.subplots(figsize=(12, 6))

    color = 'tab:red'
    ax1.set_xlabel('Dies (Episodis)')
    ax1.set_ylabel('Retard Promig (min)', color=color)
    ax1.plot(delays, color=color, linewidth=1, label='Retard')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()  
    color = 'tab:blue'
    ax2.set_ylabel('Epsilon', color=color)
    ax2.plot(epsilons, color=color, linestyle='--', label='Epsilon')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title('Entrenament amb Reset Diari')
    
    timestamp = int(time.time())
    filename = f"{save_dir}/training_reset_{timestamp}.png"
    plt.savefig(filename)
    print(f"[PLOT] Guardat a: {filename}")
    plt.close()

if __name__ == "__main__":
    train_agent()