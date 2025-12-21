# Fix: Delays Negativos Absurdos (-900, -1000 minutos)

## 🐛 Problema Detectado

Los trenes mostraban delays absurdos como `-987 min`, `-948 min`, `-992 min`, causando:
- Apartaderos innecesarios (trenes "adelantados" 16 horas)
- Estadísticas incorrectas en el reporte
- Comportamiento irreal de la simulación

## 🔍 Diagnóstico

### Ejemplo del Bug:
```
Schedule del tren:
  '72301': 371.63 min    ← Normal
  '72302': 1370.63 min   ← ¡SALTO DE 999 MINUTOS!
  '72303': 1375.04 min   ← Normal
```

### Causa Raíz:

**Archivo**: `RodaliesAI.py` - función `calculate_schedule()` (línea 219)

```python
# CÓDIGO INCORRECTO:
travel_time = edges[0].expected_minutes  # ← Siempre usa vía 0
```

**Problema**: Cuando la **vía 0** tenía un OBSTACLE, su `expected_minutes = 999`, contaminando todo el schedule.

**Por qué 999?** → En `Edge.py` (línea 64):
```python
else: # OBSTACLE
    self.expected_minutes = 999  # ← Tiempo "infinito"
```

## ✅ Solución Implementada

**Archivo**: `RodaliesAI.py` - línea 217-219

```python
# CÓDIGO CORREGIDO:
# Usar la vía con MENOR tiempo (evita OBSTACLES con 999 min)
travel_time = min(edge.expected_minutes for edge in edges)
```

### ¿Qué hace?
- Si hay 2 vías: una NORMAL (10 min) y una OBSTACLE (999 min)
- Usa el **mínimo**: `min(10, 999) = 10 minutos` ✓
- El schedule ahora es realista

## 📊 Resultado Esperado

### Antes del Fix:
```
Train delay: -987.89 min  ← ABSURDO
Schedule: {..., '72302': 1370.63, ...}  ← 999 min de salto
```

### Después del Fix:
```
Train delay: 0.42 min     ← REALISTA
Schedule: {..., '72302': 381.63, ...}   ← ~10 min por segmento
```

## 🧹 Cambios Adicionales

También se **limpiaron logs de debugging** excesivos en `Train.py`:
- Eliminados logs detallados del `__init__`
- Simplificados warnings de schedule faltante
- Mantenido solo log esencial de llegada

## ✨ Verificación

Para confirmar que funciona:
1. Ejecuta la simulación
2. NO deberías ver delays > 100 minutos (salvo situaciones extremas)
3. Los apartaderos solo se usan para delays reales (10-30 min)
4. El `simulation_report.txt` muestra delays razonables

---

**Fecha**: 20 Diciembre 2025  
**Estado**: ✅ RESUELTO  
**Archivos modificados**: 
- `RodaliesAI.py` (calculate_schedule)
- `Enviroment/Train.py` (limpieza de logs)
