# ATLAS | BSI Transporte EEUU — Puntualidad de aerolíneas

Tablero de Power BI sobre la puntualidad de las aerolíneas de EEUU: qué tan a tiempo vuelan, dónde y cuándo se demoran, y por qué.

- **Fuente:** BTS, *Reporting Carrier On-Time Performance* (transtats.bts.gov), un registro por vuelo.
- **Período:** sep-2023 a ago-2026 (36 meses, ~21 M de vuelos).
- **Marca:** ATLAS (tinta `#1D1631`, violeta `#5B3F99`, semáforo `#2E9C8F` / `#E0A526` / `#C8102E`).

## Estructura

```
BSI_Transporte_EEUU/
├─ scripts/
│  ├─ 01_descargar_preparar.py   descarga los ZIP de BTS → fVuelos.parquet (21 M vuelos) + dimensiones
│  ├─ 02_agregar.py              agrega los vuelos a tablas livianas para Power BI (≈1,2 M filas)
│  ├─ 03_generar_pbip.py         genera el proyecto Power BI (modelo TMDL + reporte PBIR + tema)
│  ├─ configurar_repo.py         activa el filtro de ruta en un clon nuevo
│  └─ git_filtro_ruta.py         filtro git del parámetro RutaDatos
├─ raw/                          ZIP mensuales de BTS (cache, se pueden borrar)
├─ data/                         Parquet que lee Power BI
├─ pbip/BSI_Transporte_EEUU.pbip abrir con Power BI Desktop
├─ Theme/AtlasDarkUI.json        tema oscuro actual (ATLAS_Theme.json y ATLAS_Tema.json: versiones anteriores)
├─ UI_Dark_App.md                rediseño Dark UI tipo app: qué incluye y limitaciones
├─ Mejoras_UI_Manual.md          revisión clara anterior (historial)
└─ capturas/                     capturas del tablero (dark/ = versión actual)
```

## Cómo usarlo

Después de clonar, una sola vez:

```
python -I scripts/configurar_repo.py
```

Power BI no admite rutas relativas. Por eso el repo guarda el parámetro `RutaDatos` con el marcador `{{RUTA_REPO}}`, y un filtro de git (`scripts/git_filtro_ruta.py`) lo reemplaza por la carpeta del clon al hacer checkout y lo vuelve a poner al hacer commit. Así ninguna ruta local llega a GitHub.

1. `python -I scripts/01_descargar_preparar.py` (opcional: `--desde 2023-09 --hasta 2026-08`)
2. `python -I scripts/02_agregar.py`
3. `python -I scripts/03_generar_pbip.py` (vuelve a generar `pbip/`: **pisa los cambios manuales**; con Power BI cerrado)
4. Abrir `pbip/BSI_Transporte_EEUU.pbip` en Power BI Desktop y hacer **Actualizar** (≈3 min).

Para agregar un mes nuevo: correr los pasos 1 (con `--hasta` actualizado) y 2, y después Actualizar en Desktop.

## Modelo (estrella, agregado)

Cargar los 21 M de vuelos uno por uno no entra en una PC con poca RAM. Por eso Power BI lee tablas agregadas
que dan exactamente los mismos totales (control: 21.111.889 vuelos, 78,62 % a tiempo).

| Tabla | Grano | Filas | Notas |
|---|---|---|---|
| `fRutasMes` | mes × aerolínea × origen × destino × causa de cancelación | 489 mil | conteos y sumas de minutos; base de casi todas las medidas |
| `fPatrones` | mes × aerolínea × día de semana × hora programada | 71 mil | mapa de calor y franjas (sin filtro por aeropuerto) |
| `fDetalle` | 1 vuelo, solo el último mes publicado | 608 mil | página de detalle |
| `Medidas` | — | — | tabla de medidas (47) |

| Dimensión | Notas |
|---|---|
| `dMes` | mes; `MesIndice` (1..36) sostiene las comparaciones contra el mes y el año anterior |
| `dDiaSemana` | lunes a domingo |
| `dAerolinea` | Troncal / Low cost / Regional |
| `dOrigen`, `dDestino` | la misma tabla de aeropuertos con dos roles: ciudad, estado y coordenadas (OurAirports) |
| `dHora` | hora programada de salida y franja horaria |
| `dCausaCancelacion` | Aerolínea, Clima, NAS, Seguridad |

## Medidas clave

| Medida | Definición |
|---|---|
| `% A Tiempo` | llegadas con menos de 15 min de demora / vuelos operados (criterio BTS) |
| `% Cancelados` | cancelados / vuelos programados |
| `Demora Promedio de Demorados` | demora media de llegada de los vuelos que llegaron 15+ min tarde |
| `Min Demora <causa>` | minutos atribuidos por BTS a Aerolínea, Clima, Sistema NAS, Seguridad, Avión previo |
| `% Causa Controlable` | (Aerolínea + Avión previo) / total de minutos con causa |
| `Δ % A Tiempo vs AA` | diferencia en puntos porcentuales contra los mismos meses del año anterior (en blanco si el período elegido incluye el primer año) |
| `% A Tiempo Móvil 3M` | promedio móvil de 3 meses |
| `Color % A Tiempo` | semáforo: ≥80% verde, ≥72% ámbar, debajo rojo |

## Páginas

1. **Resumen:** indicadores principales, tendencia mensual, ranking de aerolíneas y mapa.
2. **Aerolíneas:** tabla de desempeño, volumen, troncales contra regionales contra low cost, cancelaciones.
3. **Aeropuertos y rutas:** mapa de demoras, tabla de aeropuertos y tabla de rutas.
4. **Causas de demora:** mezcla de causas, evolución mensual, causas de cancelación.
5. **Patrones horarios:** mapa de calor día × hora, estacionalidad, franjas horarias.
6. **Detalle de vuelos:** consulta vuelo por vuelo del último mes publicado.

## Notas

- BTS publica con unos 2 a 3 meses de atraso. Solo reportan las aerolíneas con ≥0,5 % de los ingresos domésticos.
- Las causas de demora solo se informan para vuelos con 15+ min de demora de llegada.
- Las rutas y los aeropuertos con pocos vuelos pueden mostrar porcentajes extremos. Conviene filtrar por volumen.
- Los mapas usan Azure Maps (los mapas de Bing se están dando de baja en Power BI).
