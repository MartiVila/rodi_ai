import simpy
import networkx as nx
import matplotlib.pyplot as plt
import time

# --- CONFIGURACIÓN VISUAL ---
plt.ion() # Activar modo interactivo para animación
fig, ax = plt.subplots(figsize=(10, 6))

# Posiciones fijas para el gráfico (La "Y" Griega)
pos = {
    "Mataró": (0, 2),      # Arriba Izquierda
    "Granollers": (2, 2),  # Arriba Derecha
    "El_Clot": (1, 1),     # Centro (Cruce)
    "Arc_Triomf": (1, 0)   # Abajo (Destino)
}

# Estado global para la visualización
estado_vias = {} # Guardará si la vía está 'libre' o 'ocupada'
posicion_trenes = {} # Guardará dónde está cada tren

def actualizar_grafico(env, grafo):
    """Dibuja el estado actual de la red"""
    ax.clear()
    ax.set_title(f"Simulación RENFE Rodalies - Tiempo: {env.now:.1f} min")
    
    # 1. Dibujar Vías (Aristas)
    colores_vias = []
    for u, v in grafo.edges():
        # Si la vía está ocupada por algún tren, píntala ROJA, si no, VERDE
        estado = estado_vias.get((u, v), "libre")
        colores_vias.append('red' if estado == 'ocupada' else 'green')
    
    nx.draw_networkx_edges(grafo, pos, ax=ax, edge_color=colores_vias, width=4, arrowsize=20)
    
    # 2. Dibujar Estaciones (Nodos)
    nx.draw_networkx_nodes(grafo, pos, ax=ax, node_size=1000, node_color='lightgray')
    nx.draw_networkx_labels(grafo, pos, ax=ax, font_weight='bold')
    
    # 3. Dibujar Trenes (Como puntos sobre los nodos o vías)
    # Nota: SimPy no da coordenadas continuas, así que simplificamos visualizando al tren en su última ubicación
    leyenda_trenes = []
    for nombre, ubicacion in posicion_trenes.items():
        if ubicacion in pos:
            x, y = pos[ubicacion]
            # Añadimos un pequeño desplazamiento aleatorio para que no se solapen si están en la misma estación
            ax.text(x, y+0.15, f"🚆{nombre}", fontsize=10, color='blue', fontweight='bold', ha='center')
    
    plt.draw()
    plt.pause(4) # Pausa para que el ojo humano vea la animación

# --- LÓGICA DE SIMULACIÓN (SIMPY) ---

def tren(env, nombre, ruta, grafo, recursos_vias):
    # El tren empieza en el origen
    posicion_trenes[nombre] = ruta[0]
    actualizar_grafico(env, grafo)
    
    for i in range(len(ruta) - 1):
        origen = ruta[i]
        destino = ruta[i+1]
        via_id = (origen, destino)
        
        print(f"[{env.now:.1f}] {nombre} quiere entrar a tramo {origen}->{destino}")
        
        # SOLICITUD DE VÍA (El cuello de botella)
        with recursos_vias[via_id].request() as req:
            yield req # Esperar a que la vía esté libre
            
            # ¡Vía concedida!
            estado_vias[via_id] = "ocupada" 
            print(f"[{env.now:.1f}] {nombre} ENTRA en vía {origen}->{destino}")
            actualizar_grafico(env, grafo)
            
            # Simular tiempo de viaje
            tiempo_viaje = grafo[origen][destino]['weight']
            yield env.timeout(tiempo_viaje)
            
            # Llegada al siguiente nodo
            print(f"[{env.now:.1f}] {nombre} LLEGA a {destino}")
            posicion_trenes[nombre] = destino # Actualizamos posición visual
            estado_vias[via_id] = "libre"     # Liberamos la vía visualmente
            actualizar_grafico(env, grafo)

# --- CONFIGURACIÓN DEL ESCENARIO ---

def ejecutar_simulacion():
    # 1. Crear Grafo
    G = nx.DiGraph()
    G.add_edge("Mataró", "El_Clot", weight=4)       # Tarda 4 min
    G.add_edge("Granollers", "El_Clot", weight=4)   # Tarda 4 min
    G.add_edge("El_Clot", "Arc_Triomf", weight=3)   # Tarda 3 min (Cuello de botella)

    # 2. Inicializar SimPy
    env = simpy.Environment()
    recursos_vias = {edge: simpy.Resource(env, capacity=1) for edge in G.edges}

    # 3. Crear Trenes
    # TREN A: Sale de Mataró en t=0
    env.process(tren(env, "R1", ["Mataró", "El_Clot", "Arc_Triomf"], G, recursos_vias))
    
    # TREN B: Sale de Granollers en t=1 (Muy seguido del A)
    # Esto causará conflicto en "El_Clot" porque el R1 aún estará usando la vía hacia Arc de Triomf
    env.process(tren(env, "R2", ["Granollers", "El_Clot", "Arc_Triomf"], G, recursos_vias))

    # Mantener la ventana abierta al final
    print("Iniciando simulación visual...")
    env.run(until=15)
    print("Simulación terminada.")
    plt.ioff()
    plt.show()

if __name__ == "__main__":
    ejecutar_simulacion()