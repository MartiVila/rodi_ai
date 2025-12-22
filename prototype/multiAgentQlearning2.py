# -*- coding: utf-8 -*-
import random
from collections import defaultdict
import sys
import io

# Forzar UTF-8 en Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Importar configuraciones de estrategias
try:
    from config_optimal import QLConfig
    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False

# =========================
# R1 CONFIGURACIÓN
# =========================

ESTACIONES_R1 = [
    "L'Hospitalet de Llobregat",
    "Barcelona - Sants",
    "Barcelona - Pl. Catalunya",
    "Barcelona - Arc de Triomf",
    "Barcelona - El Clot",
    "St. Adrià de Besòs",
    "Badalona",
    "Montgat",
    "Montgat Nord",
    "El Masnou",
    "Ocata",
    "Premià de Mar",
    "Vilassar de Mar",
    "Cabrera de Mar - Vilassar de Mar",
    "Mataró",
    "St. Andreu de Llavaneres",
    "Arenys de Mar",
    "Canet de Mar",
    "St. Pol de Mar",
    "Calella",
    "Pineda de Mar",
    "Santa Susanna",
    "Malgrat de Mar",
    "Blanes",
    "Tordera"
]

# Tiempos entre estaciones consecutivas (en minutos) - basado en horarios reales R1
TIEMPOS_R1 = {
    ("L'Hospitalet de Llobregat", "Barcelona - Sants"): 3,
    ("Barcelona - Sants", "Barcelona - Pl. Catalunya"): 3,
    ("Barcelona - Pl. Catalunya", "Barcelona - Arc de Triomf"): 3,
    ("Barcelona - Arc de Triomf", "Barcelona - El Clot"): 3,
    ("Barcelona - El Clot", "St. Adrià de Besòs"): 4,
    ("St. Adrià de Besòs", "Badalona"): 5,
    ("Badalona", "Montgat"): 4,
    ("Montgat", "Montgat Nord"): 2,
    ("Montgat Nord", "El Masnou"): 3,
    ("El Masnou", "Ocata"): 3,
    ("Ocata", "Premià de Mar"): 3,
    ("Premià de Mar", "Vilassar de Mar"): 3,
    ("Vilassar de Mar", "Cabrera de Mar - Vilassar de Mar"): 2,
    ("Cabrera de Mar - Vilassar de Mar", "Mataró"): 3,
    ("Mataró", "St. Andreu de Llavaneres"): 4,
    ("St. Andreu de Llavaneres", "Arenys de Mar"): 4,
    ("Arenys de Mar", "Canet de Mar"): 3,
    ("Canet de Mar", "St. Pol de Mar"): 3,
    ("St. Pol de Mar", "Calella"): 3,
    ("Calella", "Pineda de Mar"): 3,
    ("Pineda de Mar", "Santa Susanna"): 3,
    ("Santa Susanna", "Malgrat de Mar"): 3,
    ("Malgrat de Mar", "Blanes"): 3,
    ("Blanes", "Tordera"): 5,
}

## NO TE SENTIT JA QUE EL TEMPS D'ARRIBADA JA CALCULA EL TEMPS DE PARADA PER ESTACIO
## DEIXEM A 0
TIEMPO_PARADA_ESTACION = 0  

ACCIONES = {
    0: "ACELERAR",
    1: "MANTENER",
    2: "FRENAR",
    3: "APARTAR (Apartadero)"
}

# Estaciones con apartadero disponibles (configurable) - principales de R1
SIDING_STATIONS_DEFAULT = {
    "Barcelona - Sants",
    "Barcelona - Arc de Triomf",
    "Badalona",
    "Mataró",
    "Arenys de Mar",
    "Calella",
    "Blanes",
}

# =========================
# DEFINICIÓN DE RUTAS
# =========================
# Cada ruta es una lista de estaciones consecutivas en la línea R1
RUTAS_DISPONIBLES = [
    # Ruta 0: Completa (L'Hospitalet - Tordera)
    ESTACIONES_R1.copy(),
    # Ruta 1: Desde Barcelona - Sants
    ESTACIONES_R1[1:],
    # Ruta 2: Desde Badalona
    ESTACIONES_R1[6:],
    # Ruta 3: Desde Mataró
    ESTACIONES_R1[14:],
    # Ruta 4: Desde Arenys de Mar
    ESTACIONES_R1[16:],
    # Ruta 5: Desde Calella
    ESTACIONES_R1[19:],
]

# =========================
# CLASE TREN (Multi-Agente)
# =========================

class Train:
    def __init__(self, train_id, start_delay=0, route_idx=None):
        self.train_id = train_id
        # Seleccionar ruta: si no se especifica, usar basada en ID
        if route_idx is None:
            route_idx = train_id % len(RUTAS_DISPONIBLES)
        self.route_idx = route_idx
        self.route = RUTAS_DISPONIBLES[route_idx]
        self.idx = 0  # índice en su ruta
        self.real_time = start_delay
        self.scheduled_time = start_delay
        self.done = False
        self.waiting_at_station = False  # True si está esperando en estación
        self.wait_time = 0  # tiempo acumulado esperando

    def reset(self, start_delay=0):
        self.idx = 0
        self.real_time = start_delay
        self.scheduled_time = start_delay
        self.done = False
        self.waiting_at_station = False
        self.wait_time = 0

    def current_segment(self):
        """Retorna el segmento actual (origen, destino) o None si terminó"""
        if self.idx >= len(self.route) - 1:
            return None
        return (self.route[self.idx], self.route[self.idx + 1])

# =========================
# Q-LEARNING AGENT (por tren)
# =========================

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
            return random.choice(list(ACCIONES.keys()))
        qs = [self.q[(state, a)] for a in ACCIONES]
        return qs.index(max(qs))

    def update(self, s, a, r, s2):
        if s2 is None:
            # Estado terminal
            self.q[(s, a)] += self.alpha * (r - self.q[(s, a)])
        else:
            max_q_next = max(self.q[(s2, a2)] for a2 in ACCIONES)
            self.q[(s, a)] += self.alpha * (r + self.gamma * max_q_next - self.q[(s, a)])

# =========================
# ENTORNO MULTI-AGENTE R1
# =========================

class MultiAgentR1Environment:
    def __init__(self, num_trains=2, train_spacing=8, p_inc=0.015, routes=None, siding_stations=None):
        """
        num_trains: número de trenes en la línea
        train_spacing: minutos de separación inicial entre trenes
        p_inc: probabilidad de incidencia por segmento
        routes: lista de índices de rutas para cada tren (None = basado en ID)
        """
        self.num_trains = num_trains
        self.train_spacing = train_spacing
        self.p_inc = p_inc
        self.trains = []
        self.agents = []
        self.occupied_segments = {}  # {segmento: train_id} para vía normal
        self.occupied_segments_reverse = {}  # {segmento: train_id} para vía contraria (adelantamientos)
        # Estaciones con apartadero (si no se especifica, usar las por defecto)
        self.siding_stations = set(siding_stations) if siding_stations else set(SIDING_STATIONS_DEFAULT)
        
        # Inicializar trenes y agentes
        for i in range(num_trains):
            # Asignar ruta: usar la proporcionada o seleccionar basada en ID
            route_idx = routes[i] if routes and i < len(routes) else None
            train = Train(train_id=i, start_delay=i * train_spacing, route_idx=route_idx)
            agent = QLearningAgent()
            self.trains.append(train)
            self.agents.append(agent)

    def reset(self):
        """Reinicia todos los trenes a su estado inicial"""
        self.occupied_segments.clear()
        self.occupied_segments_reverse.clear()
        for i, train in enumerate(self.trains):
            train.reset(start_delay=i * self.train_spacing)
        return self.get_states()

    def get_state(self, train, agent):
        """Obtiene el estado individual de un tren"""
        if train.done or train.idx >= len(train.route) - 1:
            return None

        segment = train.current_segment()
        if segment is None:
            return None

        origen, destino = segment
        diff = train.real_time - train.scheduled_time
        diff_disc = agent.discretize_diff(diff)
        
        # Verificar si el siguiente segmento está bloqueado por otro tren
        is_blocked = 1 if segment in self.occupied_segments and self.occupied_segments[segment] != train.train_id else 0

        return (origen, destino, diff_disc, is_blocked)

    def get_states(self):
        """Retorna lista de estados para todos los trenes"""
        return [self.get_state(train, agent) for train, agent in zip(self.trains, self.agents)]

    def step(self, actions):
        """
        Ejecuta un paso con las acciones de todos los agentes
        actions: lista de acciones [a0, a1, ..., an]
        retorna: (next_states, rewards, all_done)
        """
        rewards = [0.0] * self.num_trains
        self.occupied_segments.clear()
        self.occupied_segments_reverse.clear()

        # Primero, marcar segmentos ocupados segun acciones (saltar si el tren se aparta en apartadero)
        for i, train in enumerate(self.trains):
            if not train.done:
                seg = train.current_segment()
                if seg is not None:
                    origen, _ = seg
                    # Si el tren decide APARTAR (accion 3) y la estacion tiene apartadero y el tren va a tiempo/adelantado,
                    # no ocupa el siguiente segmento (deja pasar al otro tren)
                    diff_here = train.real_time - train.scheduled_time
                    if not (actions[i] == 3 and origen in self.siding_stations and diff_here <= 0):
                        self.occupied_segments[seg] = train.train_id

        # Ejecutar acciones para cada tren
        # incidents = []  # No mostrar incidencias para mejorar rendimiento
        for i, (train, action) in enumerate(zip(self.trains, actions)):
            if train.done:
                continue

            segment = train.current_segment()
            if segment is None:
                train.done = True
                continue

            origen, destino = segment
            base_time = TIEMPOS_R1[segment]
            diff = train.real_time - train.scheduled_time
            is_retrasado = diff > 1  # Tren esta en retraso
            is_blocked = segment in self.occupied_segments and self.occupied_segments[segment] != train.train_id

            # Logica de APARTADERO (accion 3)
            if action == 3:
                # Solo tiene sentido apartar en estaciones con apartadero
                if origen in self.siding_stations:
                    if diff <= 0:
                        # Verificar si es beneficioso: existe otro tren retrasado que quiere este mismo segmento
                        beneficioso = False
                        for j, other in enumerate(self.trains):
                            if j == i or other.done:
                                continue
                            other_seg = other.current_segment()
                            if other_seg == segment:
                                other_diff = other.real_time - other.scheduled_time
                                if other_diff > 1 and actions[j] != 3:
                                    beneficioso = True
                                    break
                        # El tren se aparta (no avanza, espera en estacion)
                        train.waiting_at_station = True
                        train.wait_time += 1
                        # Recompensa moderada si ayuda, pequena penalizacion si innecesario
                        rewards[i] += 20 if beneficioso else -5
                        # No avanzar el segmento
                        continue
                    else:
                        # El tren va retrasado: apartarse no tiene sentido
                        train.waiting_at_station = True
                        train.wait_time += 1
                        rewards[i] -= 10
                        continue
                else:
                    # Estacion sin apartadero: no se puede realizar la accion
                    train.waiting_at_station = True
                    train.wait_time += 1
                    rewards[i] -= 10
                    continue

            # Acciones normales (0, 1, 2)
            elif is_blocked:
                # Bloqueo: el tren debe esperar
                train.waiting_at_station = True
                train.wait_time += 1
                rewards[i] -= 50  # Penalizacion por espera
                continue
            else:
                train.waiting_at_station = False
                
                # Efecto de la accion
                if action == 0:  # ACELERAR
                    delta = -1
                elif action == 2:  # FRENAR
                    delta = 1
                else:  # MANTENER
                    delta = 0

                travel_time = max(1, base_time + delta)

            # Incidencia aleatoria
            inc_time = 0
            if random.random() < self.p_inc:
                inc_time = random.randint(3, 10)
                # incidents.append((train.train_id, origen, destino, inc_time))

            travel_time += inc_time

            # Avanza tiempo (trayecto + parada obligatoria)
            train.real_time += travel_time + TIEMPO_PARADA_ESTACION
            train.scheduled_time += base_time + TIEMPO_PARADA_ESTACION
            train.idx += 1

            # Recompensa basada en desviacion del horario
            diff = train.real_time - train.scheduled_time
            if diff == 0:
                # RECOMPENSA POSITIVA por llegar exactamente a tiempo
                rewards[i] = 100
            else:
                # Penalizacion proporcional a la desviacion
                rewards[i] = -abs(diff) - 50

            # Verificar si termino el recorrido
            if train.idx >= len(train.route) - 1:
                train.done = True

        # No mostrar incidencias (comentadas para rendimiento)
        # for tid, orig, dest, inc in incidents:
        #     print(f"INCIDENCIA! Tren {tid}: {orig} -> {dest} +{inc}min retraso")

        next_states = self.get_states()
        all_done = all(t.done for t in self.trains)

        return next_states, rewards, all_done

# =========================
# ENTRENAMIENTO MULTI-AGENTE
# =========================

def train_multiagent(num_trains=2, episodes=10000, train_spacing=8, routes=None, alpha_start=0.1, gamma=0.95, epsilon_start=0.15):
    env = MultiAgentR1Environment(num_trains=num_trains, train_spacing=train_spacing, p_inc=0.01, routes=routes)
    
    # Actualizar parámetros iniciales de los agentes
    for agent in env.agents:
        agent.gamma = gamma
        agent.epsilon = epsilon_start
    
    # Métricas de entrenamiento
    episode_rewards = []  # suma de rewards de todos los agentes
    episode_individual_rewards = [[] for _ in range(num_trains)]  # rewards por agente
    episode_epsilons = []
    q_delta_L1 = []
    q_delta_Linf = []
    q_prev = [{} for _ in range(num_trains)]

    for ep in range(episodes):
        # OPTIMIZACIÓN: Alpha decay dinámico (empieza en alpha_start, decae exponencialmente)
        current_alpha = alpha_start * (0.98 ** (ep / 100))
        
        states = env.reset()
        total_reward = 0
        individual_totals = [0.0] * num_trains
        
        # Actualizar alpha en todos los agentes
        for agent in env.agents:
            agent.alpha = current_alpha

        while not all(t.done for t in env.trains):
            # Cada agente decide su acción
            actions = []
            for i, (agent, state) in enumerate(zip(env.agents, states)):
                if state is None or env.trains[i].done:
                    actions.append(1)  # MANTENER (no importa, tren terminado)
                else:
                    actions.append(agent.action(state))

            # Ejecutar paso
            next_states, rewards, _ = env.step(actions)

            # Actualizar Q-tables
            for i, agent in enumerate(env.agents):
                if states[i] is not None and not env.trains[i].done:
                    agent.update(states[i], actions[i], rewards[i], next_states[i])
                    individual_totals[i] += rewards[i]

            states = next_states
            total_reward += sum(rewards)

        # OPTIMIZACIÓN: Decay epsilon más suave (0.99 en lugar de 0.995)
        # Esto mantiene exploración durante más episodios
        epsilon_decay = 0.99 ** (ep / 50)
        for agent in env.agents:
            agent.epsilon = max(0.01, epsilon_start * epsilon_decay)

        episode_rewards.append(total_reward)
        for i in range(num_trains):
            episode_individual_rewards[i].append(individual_totals[i])
        episode_epsilons.append(env.agents[0].epsilon)

        # Calcular diferencias de Q-Table (promedio entre agentes)
        deltas_L1 = []
        deltas_Linf = []
        for i, agent in enumerate(env.agents):
            keys = set(agent.q.keys()) | set(q_prev[i].keys())
            deltas = [abs(agent.q.get(k, 0.0) - q_prev[i].get(k, 0.0)) for k in keys]
            if deltas:
                deltas_L1.append(sum(deltas))
                deltas_Linf.append(max(deltas))
            q_prev[i] = dict(agent.q)
        
        q_delta_L1.append(sum(deltas_L1) / len(deltas_L1) if deltas_L1 else 0.0)
        q_delta_Linf.append(sum(deltas_Linf) / len(deltas_Linf) if deltas_Linf else 0.0)

        if ep % 50 == 0:
            avg_reward = total_reward / num_trains if num_trains > 0 else 0
            routes_info = ", ".join([f"T{i}:R{env.trains[i].route_idx}" for i in range(env.num_trains)])
            print(f"Episodio {ep} | Reward total: {total_reward:.2f} | Avg/tren: {avg_reward:.2f} | Epsilon: {env.agents[0].epsilon:.3f} | Rutas: {routes_info}")

    stats = {
        "episodes": episodes,
        "num_trains": num_trains,
        "train_spacing": train_spacing,
        "alpha": env.agents[0].alpha,
        "gamma": env.agents[0].gamma,
        "epsilon_final": env.agents[0].epsilon,
        "epsilon_min": 0.01,
        "p_inc": env.p_inc,
        "reward_avg": sum(episode_rewards) / len(episode_rewards) if episode_rewards else 0.0,
        "reward_min": min(episode_rewards) if episode_rewards else 0.0,
        "reward_max": max(episode_rewards) if episode_rewards else 0.0,
        "reward_last_100_avg": sum(episode_rewards[-100:]) / min(100, len(episode_rewards)) if episode_rewards else 0.0,
        "q_table_sizes": [len(agent.q) for agent in env.agents],
        "episode_rewards": episode_rewards,
        "episode_individual_rewards": episode_individual_rewards,
        "episode_epsilons": episode_epsilons,
        "q_delta_L1": q_delta_L1,
        "q_delta_Linf": q_delta_Linf,
    }

    return env, stats

# =========================
# SIMULACIÓN MULTI-AGENTE
# =========================

def simulate_multiagent(env, verbose=False):
    # Reset con epsilon=0 (greedy)
    for agent in env.agents:
        agent.epsilon = 0.0

    states = env.reset()

    if verbose:
        print("\n--- SIMULACION MULTI-AGENTE R1 ---\n")
        print("Rutas asignadas:")
        for i, train in enumerate(env.trains):
            inicio = train.route[0]
            fin = train.route[-1]
            print(f"  Tren {i}: Ruta {train.route_idx} ({inicio} -> {fin}) - Estaciones: {len(train.route)}")
        print()
    
    step_count = 0
    max_steps = 1000

    while not all(t.done for t in env.trains) and step_count < max_steps:
        # Cada agente decide su accion
        actions = []
        for i, (agent, state, train) in enumerate(zip(env.agents, states, env.trains)):
            if state is None or train.done:
                actions.append(1)  # MANTENER
            else:
                actions.append(agent.action(state))

        # Ejecutar paso
        next_states, rewards, _ = env.step(actions)
        states = next_states
        step_count += 1
        
        if verbose and step_count % 50 == 0:
            print(f"Paso {step_count}...")

    print("\n" + "=" * 80)
    print("=== Evaluacion ===")
    print(f"{'Tren':<6} | {'T.Real':<8} | {'T.Plan':<8} | {'Delta':<6} | {'Estado':<20}")
    print("-" * 80)
    delays = []
    on_time_count = 0
    for i, train in enumerate(env.trains):
        delay = train.real_time - train.scheduled_time
        delays.append(delay)
        if abs(delay) <= 1:
            estado = "A TIEMPO"
            on_time_count += 1
        elif delay > 0:
            estado = "RETRASADO"
        else:
            estado = "ADELANTADO"
        print(f"{i:<6} | {train.real_time:<8} | {train.scheduled_time:<8} | {delay:+6d} | {estado:<20}")

    # Metricas globales
    n = max(1, len(delays))
    avg_delay = sum(delays) / n
    avg_delay_abs = sum(abs(d) for d in delays) / n
    efficiency_rate = on_time_count / n

    print("-" * 80)
    print(f"Tiempo medio general (|Delta|): {avg_delay_abs:.2f} min")
    print(f"Tasa de eficiencia (a tiempo): {efficiency_rate*100:.1f}%")

    return {
        "train_delays": delays,
        "train_real_times": [t.real_time for t in env.trains],
        "train_scheduled_times": [t.scheduled_time for t in env.trains],
        "avg_delay": avg_delay,
        "avg_delay_abs": avg_delay_abs,
        "efficiency_rate": efficiency_rate,
    }

# =========================
# EVALUACIÓN MULTI-AGENTE
# =========================

def evaluate_multiagent(env, episodes=50):
    # Guardar epsilons originales
    original_epsilons = [agent.epsilon for agent in env.agents]
    
    # Evaluacion greedy
    for agent in env.agents:
        agent.epsilon = 0.0

    all_delays = [[] for _ in range(env.num_trains)]
    all_rewards = [[] for _ in range(env.num_trains)]

    for ep_idx in range(episodes):
        states = env.reset()
        individual_rewards = [0.0] * env.num_trains
        step_count = 0
        max_steps = 1000

        while not all(t.done for t in env.trains) and step_count < max_steps:
            actions = []
            for i, (agent, state) in enumerate(zip(env.agents, states)):
                if state is None or env.trains[i].done:
                    actions.append(1)
                else:
                    actions.append(agent.action(state))

            next_states, rewards, _ = env.step(actions)
            for i in range(env.num_trains):
                individual_rewards[i] += rewards[i]
            states = next_states
            step_count += 1

        for i, train in enumerate(env.trains):
            delay = train.real_time - train.scheduled_time
            all_delays[i].append(delay)
            all_rewards[i].append(individual_rewards[i])
        
        if (ep_idx + 1) % 10 == 0:
            print(f"Evaluacion: {ep_idx + 1}/{episodes} completado")

    # Restaurar epsilons
    for agent, eps in zip(env.agents, original_epsilons):
        agent.epsilon = eps

    # Metricas agregadas (globales)
    total_samples = 0
    sum_abs_delays = 0.0
    on_time_total = 0
    for i in range(env.num_trains):
        for d in all_delays[i]:
            total_samples += 1
            sum_abs_delays += abs(d)
            if abs(d) <= 1:
                on_time_total += 1

    avg_delay_abs_overall = (sum_abs_delays / total_samples) if total_samples else 0.0
    efficiency_rate_overall = (on_time_total / total_samples) if total_samples else 0.0

    eval_stats = {
        "eval_episodes": episodes,
        "delays_per_train": all_delays,
        "rewards_per_train": all_rewards,
        "avg_delay_abs_overall": avg_delay_abs_overall,
        "efficiency_rate_overall": efficiency_rate_overall,
    }

    # Agregar estadisticas resumidas
    for i in range(env.num_trains):
        eval_stats[f"train_{i}_delay_avg"] = sum(all_delays[i]) / len(all_delays[i]) if all_delays[i] else 0.0
        eval_stats[f"train_{i}_delay_min"] = min(all_delays[i]) if all_delays[i] else 0.0
        eval_stats[f"train_{i}_delay_max"] = max(all_delays[i]) if all_delays[i] else 0.0
        eval_stats[f"train_{i}_reward_avg"] = sum(all_rewards[i]) / len(all_rewards[i]) if all_rewards[i] else 0.0

    return eval_stats

# =========================
# EXPORTACIÓN ESTADÍSTICAS
# =========================

def export_stats_txt(path, train_stats, eval_stats=None):
    lines = []
    lines.append("=== Estadísticas Q-Learning Multi-Agente R1 ===")
    lines.append(f"Número de trenes: {train_stats['num_trains']}")
    lines.append(f"Separación inicial entre trenes: {train_stats['train_spacing']} min")
    lines.append(f"Episodios entrenados: {train_stats['episodes']}")
    lines.append(f"Alpha (tasa aprendizaje): {train_stats['alpha']}")
    lines.append(f"Gamma (descuento): {train_stats['gamma']}")
    lines.append(f"Epsilon final: {train_stats['epsilon_final']} (mín {train_stats['epsilon_min']})")
    lines.append(f"Probabilidad de incidencia (p_inc): {train_stats['p_inc']}")
    lines.append("")
    lines.append("-- Tamaños Q-Table por agente --")
    for i, size in enumerate(train_stats['q_table_sizes']):
        lines.append(f"Tren {i}: {size} entradas")
    lines.append("")
    lines.append("-- Recompensas entrenamiento (total todos los trenes) --")
    lines.append(f"Reward medio: {train_stats['reward_avg']:.3f}")
    lines.append(f"Reward última 100 media: {train_stats['reward_last_100_avg']:.3f}")
    lines.append(f"Reward mín/máx: {train_stats['reward_min']:.3f} / {train_stats['reward_max']:.3f}")
    lines.append("")
    lines.append("-- Convergencia Q-Table (promedio entre agentes) --")
    qL1 = train_stats.get("q_delta_L1", [])
    qLi = train_stats.get("q_delta_Linf", [])
    if qL1:
        lines.append(f"ΔQ L1 medio: {sum(qL1)/len(qL1):.6f}")
        lines.append(f"ΔQ L1 últ.100 medio: {sum(qL1[-100:])/min(100,len(qL1)):.6f}")
    if qLi:
        lines.append(f"ΔQ Linf medio: {sum(qLi)/len(qLi):.6f}")
        lines.append(f"ΔQ Linf últ.100 medio: {sum(qLi[-100:])/min(100,len(qLi)):.6f}")
    lines.append("")
    
    if eval_stats:
        lines.append("-- Evaluación (epsilon=0.0) --")
        lines.append(f"Episodios evaluación: {eval_stats['eval_episodes']}")
        for i in range(train_stats['num_trains']):
            lines.append(f"\nTren {i}:")
            lines.append(f"  Retardo medio: {eval_stats[f'train_{i}_delay_avg']:.3f} min")
            lines.append(f"  Retardo mín/máx: {eval_stats[f'train_{i}_delay_min']:.3f} / {eval_stats[f'train_{i}_delay_max']:.3f} min")
            lines.append(f"  Reward medio: {eval_stats[f'train_{i}_reward_avg']:.3f}")
        lines.append("")
    
    lines.append("-- Serie temporal por episodio --")
    lines.append("Episodio, Reward_Total, Epsilon, " + ", ".join([f"Reward_Tren_{i}" for i in range(train_stats['num_trains'])]))
    for ep_idx in range(len(train_stats["episode_rewards"])):
        reward_total = train_stats["episode_rewards"][ep_idx]
        epsilon = train_stats["episode_epsilons"][ep_idx]
        individual = [train_stats["episode_individual_rewards"][i][ep_idx] for i in range(train_stats['num_trains'])]
        individual_str = ", ".join([f"{r:.6f}" for r in individual])
        lines.append(f"{ep_idx+1}, {reward_total:.6f}, {epsilon:.6f}, {individual_str}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def export_q_deltas_plot(train_stats, path="multiagent_qtable_deltas.png"):
    """Genera un plot PNG de ΔQ (L1 y Linf) por episodio."""
    qL1 = train_stats.get("q_delta_L1", [])
    qLi = train_stats.get("q_delta_Linf", [])
    episodes = list(range(1, len(qL1) + 1))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 5))
        if qL1:
            plt.plot(episodes, qL1, label="ΔQ L1 (promedio agentes)", color="tab:blue")
        if qLi:
            plt.plot(episodes, qLi, label="ΔQ Linf (promedio agentes)", color="tab:orange")
        plt.xlabel("Episodio")
        plt.ylabel("ΔQ")
        plt.title(f"Convergencia Q-Table Multi-Agente (R1 - {train_stats['num_trains']} trenes)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(path, dpi=120)
        print(f"Plot de ΔQ guardado en: {path}")
    except Exception as exc:
        # Fallback: exportar CSV
        csv_path = path.replace(".png", ".csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("episodio,delta_L1,delta_Linf\n")
            for i in range(len(episodes)):
                d1 = f"{qL1[i]:.8f}" if i < len(qL1) else ""
                di = f"{qLi[i]:.8f}" if i < len(qLi) else ""
                f.write(f"{episodes[i]},{d1},{di}\n")
        print(f"No se pudo generar PNG ({exc}). Exportado CSV: {csv_path}")


def export_qtables_json(env, path="multiagent_qtables.json"):
    """Exporta las Q-Tables de todos los agentes a JSON."""
    import json
    
    qtables_export = {}
    for i, agent in enumerate(env.agents):
        qtable = {}
        for (state, action), value in agent.q.items():
            key = f"{state}|{action}"
            qtable[key] = value
        qtables_export[f"train_{i}"] = {
            "q_table_size": len(agent.q),
            "q_values": qtable
        }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "num_trains": env.num_trains,
            "train_spacing": env.train_spacing,
            "alpha": env.agents[0].alpha,
            "gamma": env.agents[0].gamma,
            "epsilon": env.agents[0].epsilon,
            "agents": qtables_export
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Q-Tables multi-agente exportadas a: {path}")


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    # ========== MENÚ INTERACTIVO DE ESTRATEGIAS ==========
    print("=" * 80)
    print("SELECCIONA LA ESTRATEGIA DE PARÁMETROS PARA Q-LEARNING")
    print("=" * 80)
    print()
    print("Estrategias disponibles:")
    print()
    print("1) QUICK (Rapido)")
    print("   - Episodios: 7500")
    print("   - Alpha: 0.1 -> 0.02")
    print("   - Gamma: 0.95")
    print("   - Epsilon: 0.15 -> 0.01")
    print("   - Tiempo: 5-10 minutos")
    print("   Ideal para pruebas rapidas")
    print()
    print("2) DEEP (Profundo - RECOMENDADO)")
    print("   - Episodios: 10000")
    print("   - Alpha: 0.1 -> 0.015")
    print("   - Gamma: 0.95")
    print("   - Epsilon: 0.15 -> 0.005")
    print("   - Tiempo: 20-30 minutos")
    print("   Mejor convergencia y eficiencia (97-98%)")
    print()
    print("3) AGGRESSIVE (Agresivo)")
    print("   - Episodios: 8000")
    print("   - Alpha: 0.12 -> 0.03")
    print("   - Gamma: 0.93")
    print("   - Epsilon: 0.2 -> 0.02")
    print("   - Tiempo: 15-20 minutos")
    print("   Maxima exploracion, ideal para apartaderos")
    print()
    print("4) CONSERVATIVE (Conservador)")
    print("   - Episodios: 12000")
    print("   - Alpha: 0.08 -> 0.01")
    print("   - Gamma: 0.97")
    print("   - Epsilon: 0.1 -> 0.005")
    print("   - Tiempo: 40-50 minutos")
    print("   Maxima estabilidad, solucion mas robusta")
    print()
    
    # Pedir selección
    while True:
        try:
            choice = input("Selecciona (1/2/3/4) o presiona ENTER para usar DEEP: ").strip()
            if choice == "":
                choice = "2"
            choice = int(choice)
            if choice not in [1, 2, 3, 4]:
                print("Opcion no valida. Intenta de nuevo (1-4).")
                continue
            break
        except ValueError:
            print("Ingresa un numero valido (1-4).")
            continue
    
    # Configurar parámetros según la selección
    strategies = {
        1: {
            "name": "QUICK",
            "episodes": 7500,
            "train_spacing": 8,
            "alpha_start": 0.1,
            "gamma": 0.95,
            "epsilon_start": 0.15,
        },
        2: {
            "name": "DEEP",
            "episodes": 10000,
            "train_spacing": 8,
            "alpha_start": 0.1,
            "gamma": 0.95,
            "epsilon_start": 0.15,
        },
        3: {
            "name": "AGGRESSIVE",
            "episodes": 8000,
            "train_spacing": 8,
            "alpha_start": 0.12,
            "gamma": 0.93,
            "epsilon_start": 0.2,
        },
        4: {
            "name": "CONSERVATIVE",
            "episodes": 12000,
            "train_spacing": 8,
            "alpha_start": 0.08,
            "gamma": 0.97,
            "epsilon_start": 0.1,
        },
    }
    
    config = strategies[choice]
    
    print()
    print("=" * 80)
    print(f"ESTRATEGIA SELECCIONADA: {config['name']}")
    print("=" * 80)
    print(f"Episodios: {config['episodes']}")
    print(f"Train spacing: {config['train_spacing']} min")
    print(f"Alpha inicial: {config['alpha_start']}")
    print(f"Gamma: {config['gamma']}")
    print(f"Epsilon inicial: {config['epsilon_start']}")
    print()
    
    NUM_TRAINS = 12
    TRAIN_SPACING = config['train_spacing']
    EPISODES = config['episodes']
    ALPHA_START = config['alpha_start']
    GAMMA = config['gamma']
    EPSILON_START = config['epsilon_start']
    
    # Definir rutas específicas para cada tren (opcional)
    ROUTES = None

    print(f"=== Entrenamiento Multi-Agente: {NUM_TRAINS} trenes ===\n")
    print(f"Rutas disponibles: {len(RUTAS_DISPONIBLES)}")
    for i, ruta in enumerate(RUTAS_DISPONIBLES):
        print(f"  Ruta {i}: {ruta[0]} -> {ruta[-1]} ({len(ruta)} estaciones)")
    print()
    
    env, train_stats = train_multiagent(
        num_trains=NUM_TRAINS,
        episodes=EPISODES,
        train_spacing=TRAIN_SPACING,
        routes=ROUTES,
        alpha_start=ALPHA_START,
        gamma=GAMMA,
        epsilon_start=EPSILON_START
    )
    
    print("\n=== Evaluación ===")
    eval_stats = evaluate_multiagent(env, episodes=50)
    
    # Exportar estadísticas
    export_path = "multiAgentData\\multiagent_training_stats.txt"
    export_stats_txt(export_path, train_stats, eval_stats)
    print(f"\nEstadísticas exportadas a: {export_path}")

    # Plot de convergencia
    export_q_deltas_plot(train_stats, path="multiAgentData\\multiagent_qtable_deltas.png")
    
    # Exportar Q-Tables
    export_qtables_json(env, path="multiAgentData\\multiagent_qtables.json")

    # Simulación
    print("\n" + "="*80)
    sim_info = simulate_multiagent(env)

