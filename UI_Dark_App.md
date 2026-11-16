# ATLAS Dark Executive UI: rediseño tipo app

Rediseño del 16/11/2026. Reemplaza la revisión clara de `Mejoras_UI_Manual.md`, que queda como historial. Todo se genera con `scripts/03_generar_pbip.py`, así que regenerar `pbip/` no pierde nada de lo que describe este documento. Capturas en `capturas/dark/`.

## Qué quedó implementado (y verificado en Power BI Desktop)

| Pedido | Estado | Notas |
|---|---|---|
| Tema oscuro `Theme/AtlasDarkUI.json` registrado en `report.json` | ✅ | Lienzo `#0B0E14`, tarjetas `#131722` con borde `#1E293B`, radio 12, padding 16, paleta violeta/cian/esmeralda/ámbar/coral/azul, Segoe UI, texto `#F8FAFC` / `#94A3B8`. |
| Página 0 "Portada" | ✅ | Fondo PNG generado por el script (grilla radar, resplandores violeta y cian, arcos de rutas), marca y badge, título, 3 KPIs tipo vidrio y 7 lanzadores con efecto al pasar el mouse que navegan a cada módulo. |
| App Shell: barra de 48 px | ✅ | Logo ATLAS (vuelve a la portada), píldoras de navegación con la página activa en `#7C4DFF`, **Filtros (N)** con contador dinámico y **Reset**, que borra todos los segmentadores. |
| Cajón de filtros deslizable | ✅ | Grupo lateral derecho de 300 px con borde violeta, título y ✕. Se eliminó la fila fija de segmentadores y los gráficos ganaron ese alto. Dos marcadores por página (`Abrir_Filtros` / `Cerrar_Filtros`) con `suppressData` y `applyOnlyToTargetVisuals`. |
| Logos de aerolíneas | ✅ (insignia IATA) | Columna `dAerolinea[Logo_SVG_URL]` (`ImageUrl`) más `Color_Marca`. Es un emblema propio: código IATA sobre el color de la marca, con un ala geométrica. No imita los logos oficiales. |
| `Dim_Aerolineas` | ✅ (como `dAerolinea`) | No se creó una segunda dimensión, porque duplicaría los caminos de filtro hacia los hechos. Se agregaron las columnas a `dAerolinea`, que ya usaba el código IATA como clave. |
| Medidas SVG | ✅ | `KPI_Sparkline_Puntualidad_SVG`, `KPI_Bullet_Meta_SVG`, `Tabla_Barra_Puntualidad_SVG`, `Tabla_Badge_Variacion_SVG`, `Vuelo_Estado_Badge_SVG`, más `Benchmark_Hero_SVG`, `Selector_Aerolinea_SVG` y `Tooltip_Top3_Rutas_SVG`. Todas usan comillas simples dentro del SVG, números con `FORMAT(…, "en-US")` y `%`/`#` codificados en el data URI. |
| Página Benchmark | ✅ | Button Slicer con insignia y % a tiempo con semáforo, perfil de la aerolínea con ranking y 4 KPIs contra la industria, cuadrante escala vs. puntualidad con líneas de promedio, evolución vs. promedio de la industria (línea punteada gris) y ranking con logos, barras y badges. |
| Resumen | ✅ | KPIs en Tarjeta Nueva con acento cian; sparkline en "% a tiempo" y barra contra la meta del 80 % en "Δ 12 meses". Mapa en gris oscuro. |
| Tooltip de aeropuerto | ✅ | Página oculta de 320×200 con aeropuerto, % a tiempo y las 3 rutas más demoradas (rutas con 300+ vuelos). Está enlazada al mapa y a la tabla de aeropuertos. |
| Parámetro de campo del mapa de calor | ✅ | `Selector_Metrica_Heatmap` alterna entre % demorados, demora media (min) y % cancelados, con botones en la cabecera de la matriz. Cada métrica tiene su escala de color. Para la demora media se agregaron los minutos a `fPatrones` en `02_agregar.py`. |
| Detalle de vuelos | ✅ | Las columnas Cancelado, Causa y Desviado se reemplazaron por el badge de estado (a tiempo, demora 15–60, demora >60, desviado, cancelado con su causa). |

## Diferencias con lo pedido

- **Logos**: insignias propias en lugar de logos oficiales, tal como se decidió.
- **Color de marca en la línea de evolución**: Power BI no permite colorear una serie de línea con una medida. La aerolínea seleccionada va en cian y el promedio de la industria en gris punteado.
- **Filtros (N)** cuenta también las selecciones hechas sobre los gráficos, por ejemplo al hacer clic en una burbuja del mapa. DAX no distingue un filtro de segmentador de uno cruzado.
- **Detalle de vuelos** tarda entre 30 y 60 segundos en cargar la primera vez (608 mil vuelos con un SVG por fila visible).
- En Desktop los botones se activan con **Ctrl+clic**. En el Servicio y en modo lectura, con clic normal.

## Cómo regenerar

Con Power BI cerrado:

```
python -I scripts/02_agregar.py      # solo si cambiaron los datos (ahora incluye minutos de demora en fPatrones)
python -I scripts/03_generar_pbip.py
```

Después abrir `pbip/BSI_Transporte_EEUU.pbip`, hacer **Actualizar** (≈3 min) y guardar.
