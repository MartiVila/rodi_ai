import time
import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict

# Imports del teu entorn
from Enviroment.TrafficManager import TrafficManager
from Enviroment.Train import Train
from Agent.QlearningAgent import QLearningAgent

class RodaliesTraining:
    """
    Classe encarregada de gestionar l'entrenament intensiu. SENSE INTERFÍCIE GRÀFICA.
    
    Responsabilitats:
    1. Executar simulacions sense renderitzat gràfic.
    2. Gestionar el 'Grid Search' per tal d'explorar diferents possibles situacions. 
    3. Implementar el sistema de 'Curriculum Learning' (dificultat progressiva).
    4. Generar informes i gràfics de rendiment.
    """

    # === Parametres Globals ===
    OUTPUT_DIR = "Enviroment/informe_exhaustiu"
    PLOTS_DIR = "Agent/Plots_Exhaustius"
    BRAINS_DIR = "Agent/Qtables"
    
    TOTAL_DAYS = 10000       
    MINUTES_PER_DAY = 1440 
    SAVE_INTERVAL = 1000      


    # Convergencia de la Q-Table
    CONVERGENCE_INTERVAL_DAYS = 100
    CONVERGENCE_ATOL = 1e-6

    # Hiperparàmetres a provar
    HYPERPARAMS_GRID = [
        # Percentatge en que es manté el epsilon (Si decay_epsilon == 0.8 es manté el 80% per iteració)
        {'alpha': 0.9,  'gamma': 0.99, 'epsilon_decay': 0.8,  'label': 'Agressiu (a=0.9)'},
        {'alpha': 0.7,  'gamma': 0.99, 'epsilon_decay': 0.5,  'label': 'Equilibrat (a=0.7)'},
        {'alpha': 0.3,  'gamma': 0.99, 'epsilon_decay': 0.2,  'label': 'Estratègic (a=0.3)'},
        {'alpha': 0.1,  'gamma': 0.99, 'epsilon_decay': 0.8,  'label': 'Personalitzat (a=0.1)'}
    ]

    def __init__(self):
        """Inicialitza l'entorn de treball i crea els directoris necessaris."""
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.PLOTS_DIR, exist_ok=True)
        os.makedirs(self.BRAINS_DIR, exist_ok=True)

    """
    ############################################################################################
    ############################################################################################

    Configuració del Curriculum Learning

    ############################################################################################
    ############################################################################################
    """

    def _setup_curriculum(self, manager):
        """
        Defineix els nivells de dificultat progressiva per a l'entrenament.
        
        Estratègia:
        Divideix la línia R1 en segments petits per aprendre les connexions locals,
        i després expandeix a trams acumulatius fins a cobrir tota la línia.
        
        :param manager: Instància de TrafficManager per modificar les línies.
        :return: Llista ordenada de claus (strings) que representen els nivells.
        """
        # Assumim que el manager ja ha carregat la R1 completa
        if 'R1_NORD' not in manager.lines:
            # Fallback si el manager no ha carregat dades (depèn de la impl. de TrafficManager)
            print("[ALERTA] R1_NORD no trobada, curriculum pot fallar.")
            return []

        full_route_nord = manager.lines['R1_NORD'] 
        
        def create_level(name, stations_slice):
            #fem l'anada
            manager.lines[name] = stations_slice
            #Ara aqui tenim la tornada
            manager.lines[f"{name}_SUD"] = stations_slice[::-1]

        # --- DEFINICIÓ DE NIVELLS (Con ida y vuelta) ---
        create_level('NIVELL_1', full_route_nord[:5])
        create_level('NIVELL_2', full_route_nord[5:10])
        create_level('NIVELL_3', full_route_nord[:10])
        create_level('NIVELL_4', full_route_nord[10:15])
        create_level('NIVELL_5', full_route_nord[:15])
        create_level('NIVELL_6', full_route_nord)        
        
        print(f"[Curriculum] 6 Nivells BIDIRECCIONALS generats.")
        
        return ['NIVELL_1', 'NIVELL_2', 'NIVELL_3', 'NIVELL_4', 'NIVELL_5', 'NIVELL_6']

    """
    ############################################################################################
    ############################################################################################

    Bucle d'Entrenament

    ############################################################################################
    ############################################################################################
    """
    #TEMPS PAS MES RAPID
    DT_STEP = 2.0

    def run_experiment(self, params):
        """
        Executa UNA simulació completa (8000 dies) amb uns paràmetres concrets.
        
        :param params: Diccionari amb alpha, gamma, epsilon_decay i label.
        :return: Tupla (historial_retards, logs_trens, manager_final).
        """
        print(f"\n>>> INICIANT EXPERIMENT: {params['label']} <<<")

        safe_label = params['label'].replace(' ', '_').replace('(', '').replace(')', '').replace('=', '')
        
        brain_filename = f"q_table.pkl"
        brain_path = os.path.join(self.BRAINS_DIR, brain_filename)
        brain_json_path = os.path.join(self.BRAINS_DIR, "q_table.json")

        manager = TrafficManager(width=1000, height=1000, is_training=True)
        
        initial_epsilon = 1.0
        
        manager.brain = QLearningAgent(
            alpha=params['alpha'], 
            gamma=params['gamma'], 
            epsilon=initial_epsilon 
        )

        # Intentem carregar taula prèvia si existeix
        manager.brain.load_table(filename=brain_path)
        
        # 3. Setup Curriculum
        curriculum_levels = self._setup_curriculum(manager)
        days_per_level = self.TOTAL_DAYS // len(curriculum_levels)
        
        history_avg_delay = []
        start_time = time.time()
        current_level_idx = 0

        # Per a la convergència de la Q-Table
        convergence_rows = []
        prev_q_snapshot = manager.brain.qtable_snapshot()

        for day in range(1, self.TOTAL_DAYS + 1):
            
            # Calculem quin nivell toca segons el dia actual
            new_level_idx = min((day - 1) // days_per_level, len(curriculum_levels) - 1)
            
            if new_level_idx != current_level_idx or day == 1:
                current_level_idx = new_level_idx
                level_name = curriculum_levels[current_level_idx]
                
                # Actualitzem la línia de spawn del manager
                manager.current_spawn_line = level_name 
                
                # Reset d'exploració al canviar de nivell (important per aprendre el nou tram)
                manager.brain.epsilon = 1.0 
                print(f"\n*** [Dia {day}] CURRICULUM LEVEL UP! -> {level_name} ***")

            # RESET DIARI D'ENTORN
            manager.active_trains.clear()
            manager.completed_train_logs.clear()

            if hasattr(TrafficManager, '_train_positions'):
                TrafficManager._train_positions.clear()
            
            manager.sim_time = 0.0
            manager.last_spawn = -manager.SPAWN_INTERVAL
            manager.reset_network_status()
            
            delays_in_step = []
            steps_per_day = int(self.MINUTES_PER_DAY // self.DT_STEP)

            # Executem 1440 minuts simulats
            for _ in range(steps_per_day):
                manager.update(dt_minutes=self.DT_STEP) 
                
                # Recollida de mètriques en temps real
                if manager.active_trains:
                    # Calculem retard absolut actual
                    step_delays = [abs(t.calculate_delay()) for t in manager.active_trains]
                    delays_in_step.append(np.mean(step_delays))
            
            daily_avg = np.mean(delays_in_step) if delays_in_step else 0
            history_avg_delay.append(daily_avg)

            if day % 100 == 0:
                manager.brain.decay_epsilon(params['epsilon_decay'], min_epsilon=0.01)
            
            if day % 100 == 0:
                elapsed = time.time() - start_time
                days_left = self.TOTAL_DAYS - day
                rate = day / elapsed if elapsed > 0 else 0
                eta_min = (days_left / rate) / 60 if rate > 0 else 0
                
                print(f"   Dia {day:05d} [{curriculum_levels[current_level_idx]}] "
                      f"| Eps: {manager.brain.epsilon:.4f} | Retard: {daily_avg:.2f}m "
                      f"| ETA: {eta_min:.1f} min")
                
            # convergencia Qtable
            if day % self.CONVERGENCE_INTERVAL_DAYS == 0:
                curr_q_snapshot = manager.brain.qtable_snapshot()
                metrics = QLearningAgent.qtable_convergence_metrics(
                    prev_q_snapshot,
                    curr_q_snapshot,
                    atol=self.CONVERGENCE_ATOL,
                )
                convergence_rows.append({
                    "day": day,
                    "level": curriculum_levels[current_level_idx],
                    "epsilon": float(manager.brain.epsilon),
                    "daily_avg_delay": float(daily_avg),
                    **metrics,
                })
                prev_q_snapshot = curr_q_snapshot
            

            if day % self.SAVE_INTERVAL == 0:
                manager.brain.save_table(brain_path)
                manager.brain.export_qtable_to_json(brain_json_path)

        # Guardat final en acabar l'experiment
        manager.brain.save_table(brain_path)
        manager.brain.export_qtable_to_json(brain_json_path)

        # Guardem dades de convergència
        self._save_qtable_convergence(convergence_rows, safe_label)

        self._save_complete_csv(manager.completed_train_logs, params)
        return history_avg_delay, manager.completed_train_logs, manager
    

    def _save_qtable_convergence(self, convergence_rows, safe_label):
        """Guarda un CSV i un PNG de la convergència de la Q-Table (deltas entre snapshots)."""
        if not convergence_rows:
            print("[Convergència] Sense dades (convergence_rows buit).")
            return

        df = pd.DataFrame(convergence_rows)

        # CSV
        csv_path = os.path.join(self.OUTPUT_DIR, f"QTABLE_CONVERGENCE_{safe_label}.csv")
        df.to_csv(csv_path, sep=';', index=False, encoding='utf-8')

        # PNG
        plot_path = os.path.join(self.PLOTS_DIR, f"qtable_convergence_{safe_label}.png")
        plt.figure(figsize=(14, 9))

        ax1 = plt.gca()
        ax1.plot(df["day"], df["mean_abs_delta"], label="mean_abs_delta", linewidth=2)
        ax1.plot(df["day"], df["max_abs_delta"], label="max_abs_delta", linewidth=1.5, alpha=0.9)
        ax1.set_xlabel("Dia")
        ax1.set_ylabel("ΔQ (abs)")
        ax1.set_yscale('log')
        ax1.grid(True, alpha=0.25)

        ax2 = ax1.twinx()
        ax2.plot(df["day"], df["entries"], label="entries", color="tab:green", linewidth=1.5, alpha=0.9)
        ax2.set_ylabel("Mida Q-Table (entrades)")

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="best")

        plt.title("Convergència Q-Table (deltas entre snapshots)")
        plt.tight_layout()
        plt.savefig(plot_path, dpi=300)

        print(f"[Convergència] CSV guardat: {csv_path}")
        print(f"[Convergència] PNG guardat: {plot_path}")


    """
    ############################################################################################
    ############################################################################################

    Generació d'Informes i Gràfics

    ############################################################################################
    ############################################################################################
    """

    def _save_report(self, logs, params, history):
        """Genera un fitxer de text amb estadístiques detallades de l'experiment."""
        safe_label = params['label'].replace(' ', '_').replace('(', '').replace(')', '').replace('=', '')
        filename = f"{self.OUTPUT_DIR}/report_{safe_label}.txt"
        
        # Mètriques finals (últims 1000 dies per estabilitat)
        final_subset = history[-1000:] if len(history) >= 1000 else history
        final_avg = np.mean(final_subset)
        stability = np.std(final_subset)
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"=== INFORME EXHAUSTIU: {params['label']} ===\n")
            f.write(f"Dies simulats: {self.TOTAL_DAYS}\n")
            f.write(f"Retard Final (Mitjana últims 1000 dies): {final_avg:.4f} min\n")
            f.write(f"Estabilitat (Std Dev): {stability:.4f} min\n")
            f.write(f"Epsilon Decay Rate: {params['epsilon_decay']}\n\n")
            
            if logs:
                f.write(f"--- MOSTRA DE L'ÚLTIM TREN (Dia {self.TOTAL_DAYS}) ---\n")
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

    def _save_complete_csv(self, logs, params):
        """
        Genera un CSV massiu amb cada parada de cada tren.
        Format: TrenID, Dia, Estació, Hora_Prevista, Hora_Real, Retard, Estat
        """
        import csv
        safe_label = params['label'].replace(' ', '_').replace('(', '').replace(')', '').replace('=', '')
        filename = f"{self.OUTPUT_DIR}/FULL_DATA_{safe_label}.csv"
        
        print(f"Generant CSV complet ({len(logs)} trens registrats)...")
        
        with open(filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';') # Punt i coma per Excel europeu
            
            # Capçalera
            writer.writerow(['Tren_ID', 'Origen_Global', 'Desti_Global', 'Estacio', 'Ordre', 'Previst', 'Real', 'Retard_Min', 'Estat'])
            
            for train_data in logs:
                # Dades generals del tren
                # Assumim que l'ID del tren pot ser llarg, agafem els últims digits o l'hash
                t_id = train_data.get('id', 0)
                # Reconstruim la ruta ordenada
                schedule_map = train_data.get('schedule', {})
                actuals_map = train_data.get('actuals', {})
                route_names = train_data.get('route_map', {})
                
                # Ordenem les estacions per hora prevista per saber l'ordre
                sorted_schedule = sorted(schedule_map.items(), key=lambda x: x[1])
                
                if not sorted_schedule: continue
                
                origin_name = route_names.get(sorted_schedule[0][0], "?")
                dest_name = route_names.get(sorted_schedule[-1][0], "?")
                
                for idx, (node_id, expected_time) in enumerate(sorted_schedule):
                    station_name = route_names.get(node_id, f"Node_{node_id}")
                    actual_time = actuals_map.get(station_name)
                    
                    if actual_time:
                        delay = actual_time - expected_time
                        status = "PUNTUAL"
                        if delay > 2: status = "TARD"
                        if delay > 10: status = "MOLT TARD"
                        if delay < -2: status = "AVANÇAT"
                        
                        writer.writerow([
                            t_id, origin_name, dest_name, 
                            station_name, idx + 1, 
                            f"{expected_time:.2f}", f"{actual_time:.2f}", 
                            f"{delay:.2f}", status
                        ])
                    else:
                        writer.writerow([
                            t_id, origin_name, dest_name, 
                            station_name, idx + 1, 
                            f"{expected_time:.2f}", "---", 
                            "---", "CANCEL·LAT/NO ARRIBAT"
                        ])
                        
        print(f"[Informe] CSV Complet guardat a: {filename}")

    def run_grid_search(self):
        """
        Mètode principal. Itera sobre totes les configuracions d'hiperparàmetres,
        executa els experiments i genera el gràfic comparatiu final.
        """
        print(f"=== INICIANT GRID SEARCH EXHAUSTIU ({self.TOTAL_DAYS} dies) ===")
        results = {}
        
        # Configuració del gràfic
        plt.figure(figsize=(15, 10))
        
        # Iterem per cada configuració
        for params in self.HYPERPARAMS_GRID:
            history, logs, _ = self.run_experiment(params)
            results[params['label']] = history
            
            # Guardem informe individual
            self._save_report(logs, params, history)
            
            # Afegim la corba al gràfic (suavitzada amb mitjana mòbil)
            data_series = pd.Series(history)
            smooth_data = data_series.rolling(window=200).mean()
            plt.plot(smooth_data, label=f"{params['label']}", linewidth=2)

        history, logs, _ = self.run_experiment(self.HYPERPARAMS_GRID[3][0])
        results[self.HYPERPARAMS_GRID[3]['label']] = history

        self._save_report(logs, self.HYPERPARAMS_GRID[3], history)

        data_series = pd.Series(history)
        smooth_data = data_series.rolling(window=200).mean()
        plt.plot(smooth_data, label=f"{self.HYPERPARAMS_GRID[3]['label']}", linewidth=2)

        # Dibuixem línies verticals per marcar el canvi de nivells del Curriculum
        # Necessitem saber quants nivells hi ha (assumim 6 segons _setup_curriculum)
        levels_count = 6 
        days_per_level = self.TOTAL_DAYS / levels_count
        for i in range(1, levels_count):
            plt.axvline(x=i*days_per_level, color='k', linestyle='--', alpha=0.3, 
                       label='Nivell Up' if i==1 else "")

        # Format del gràfic
        plt.xlabel('Dies (Episodis)')
        plt.ylabel('Retard Promig (Mitjana Mòbil 200 dies)')
        plt.title(f'Comparativa Q-Learning amb Curriculum ({self.TOTAL_DAYS} dies)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Guardar gràfic
        plot_path = f"{self.PLOTS_DIR}/curriculum_comparison.png"
        plt.savefig(plot_path, dpi=300)
        print(f"\n[GRÀFIC FINAL] Guardat a: {plot_path}")
        print("\n=== EXPERIMENT FINALITZAT ===")

    def personal_training(self):
        """
        Mètode principal. Itera sobre totes les configuracions d'hiperparàmetres,
        executa els experiments i genera el gràfic comparatiu final.
        """
        print(f"=== INICIANT GRID SEARCH EXHAUSTIU ({self.TOTAL_DAYS} dies) ===")
        results = {}
        
        # Configuració del gràfic
        plt.figure(figsize=(15, 10))
        
        # Configuracio personalitzada
        history, logs, _ = self.run_experiment(self.HYPERPARAMS_GRID[3])
        results[self.HYPERPARAMS_GRID[3]['label']] = history

        self._save_report(logs, self.HYPERPARAMS_GRID[3], history)

        data_series = pd.Series(history)
        smooth_data = data_series.rolling(window=200).mean()
        plt.plot(smooth_data, label=f"{self.HYPERPARAMS_GRID[3]['label']}", linewidth=2)

        # Dibuixem línies verticals per marcar el canvi de nivells del Curriculum
        # Necessitem saber quants nivells hi ha (assumim 6 segons _setup_curriculum)
        levels_count = 6 
        days_per_level = self.TOTAL_DAYS / levels_count
        for i in range(1, levels_count):
            plt.axvline(x=i*days_per_level, color='k', linestyle='--', alpha=0.3, 
                       label='Nivell Up' if i==1 else "")

        # Format del gràfic
        plt.xlabel('Dies (Episodis)')
        plt.ylabel('Retard Promig (Mitjana Mòbil 200 dies)')
        plt.title(f'Comparativa Q-Learning amb Curriculum ({self.TOTAL_DAYS} dies)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Guardar gràfic
        plot_path = f"{self.PLOTS_DIR}/curriculum_comparison.png"
        plt.savefig(plot_path, dpi=300)
        print(f"\n[GRÀFIC FINAL] Guardat a: {plot_path}")
        print("\n=== EXPERIMENT FINALITZAT ===")

if __name__ == "__main__":
    trainer = RodaliesTraining()
    #trainer.run_grid_search()

    # Entrenament personalitzat
    trainer.personal_training()