# Sistema de Apartaderos (Sidings) - Rodalies AI

## 🚂 Descripción

Se ha implementado un sistema realista de **apartaderos ferroviarios** que permite a los trenes apartarse estratégicamente para mejorar el flujo del tráfico, similar a los sistemas ferroviarios reales.

## 🎯 Funcionalidades Implementadas

### 1. **Estaciones con Apartaderos**

Se han designado 4 estaciones principales de la línea R1 con capacidad de apartadero:

- **Sant Feliu de Llobregat** - Estación importante
- **Cornellà** - Nudo ferroviario
- **Barcelona Sants** - Estación principal
- **Plaça de Catalunya** - Estación central

Cada apartadero puede albergar hasta **2 trenes simultáneamente**.

### 2. **Criterios para Apartarse**

Un tren decide apartarse automáticamente cuando:

#### Caso 1: Adelanto Excesivo (>10 min)
- El tren llega **más de 10 minutos antes** de lo previsto
- Se aparta para sincronizar con el horario
- **Tiempo de espera**: 50% del adelanto

#### Caso 2: Retraso + Tren Rápido Detrás (>15 min)
- El tren tiene **más de 15 minutos de retraso**
- Hay otro tren **cerca detrás** (>70% del segmento) que va más rápido
- Se aparta para dejar pasar
- **Tiempo de espera**: 8 minutos

### 3. **Visualización**

#### Colores de los Trenes:
- 🟢 **Verde**: Tren a tiempo
- 🟠 **Naranja**: Tren en apartadero
- 🔵 **Azul**: Cediendo paso (sin apartadero)
- 🟣 **Magenta**: Esperando reparación de vía
- 🟡 **Amarillo**: Estación con trenes apartados

#### Estaciones:
- Las estaciones con apartadero se muestran con un **rectángulo gris** alrededor
- Cambian a **amarillo** cuando tienen trenes apartados
- Los trenes apartados se dibujan ligeramente desplazados (+10px)

### 4. **HUD Mejorado**

El HUD ahora muestra:
```
Dia 0 | 12:34 | Trens: 5 | Apartats: 2 | Scale: x10
```

Además incluye una **leyenda de colores** en la esquina superior izquierda.

### 5. **Estadísticas en el Reporte**

El archivo `simulation_report.txt` ahora incluye:
- **Total de usos de apartaderos** durante la simulación
- **Lista de estaciones con apartaderos**
- Información detallada de cada tren completado

Ejemplo:
```
Total Completed Trains: 49
Simulation Time Ended: 1525.09 min
Siding Uses (Apartaderos): 12

Stations with Sidings:
  - Sant Feliu de Llobregat (ID: 72303)
  - Cornellà (ID: 78804)
  - Barcelona Sants (ID: 78805)
  - Plaça de Catalunya (ID: 79400)
```

## 🔧 Archivos Modificados

1. **`Enviroment/Node.py`**
   - Añadido `has_siding` (bool)
   - Añadido `trains_in_siding` (lista)
   - Mejora visual con rectángulos

2. **`Enviroment/Train.py`**
   - Añadido `is_in_siding` (estado)
   - Añadido `siding_entry_time` y `siding_wait_duration`
   - Lógica de decisión en `arrive_at_station()`
   - Lógica de espera en `update()`
   - Limpieza al finalizar ruta

3. **`RodaliesAI.py`**
   - Lista `stations_with_sidings`
   - Asignación de apartaderos durante `load_real_data()`
   - Contador `siding_usage_count`
   - HUD mejorado con leyenda
   - Estadísticas en `generate_report()`

## 📊 Beneficios del Sistema

1. **Realismo**: Replica el comportamiento real de líneas ferroviarias
2. **Eficiencia**: Reduce congestión permitiendo adelantamientos
3. **Flexibilidad**: Los trenes adelantados esperan para mantener horarios
4. **Prevención**: Evita colisiones cuando un tren lento bloquea la vía
5. **Datos**: Estadísticas detalladas sobre el uso del sistema

## 🚀 Próximas Mejoras Posibles

- [ ] Apartaderos dinámicos (capacidad variable)
- [ ] Coste económico de usar apartaderos (para el Q-Learning)
- [ ] Prioridad de trenes (expresos vs. locales)
- [ ] Apartaderos de emergencia (averías)
- [ ] Optimización IA para decidir cuándo apartarse

## 🎮 Cómo Usar

Simplemente ejecuta la simulación:
```bash
python RodaliesAI.py
```

El sistema funcionará automáticamente. Los trenes tomarán decisiones inteligentes sobre cuándo apartarse basándose en los criterios programados.

---

**Autor**: Sistema de IA Rodalies  
**Fecha**: Diciembre 2025  
**Versión**: 2.0 - Apartaderos
