"""
ATLAS | BSI Transporte EEUU
Genera el proyecto Power BI (PBIP): modelo semántico TMDL + reporte PBIR + tema ATLAS Dark Executive UI.

Uso: python -I 03_generar_pbip.py
Salida: ../pbip/BSI_Transporte_EEUU.pbip  (abrir con Power BI Desktop y Actualizar)
"""
import json
import math
import shutil
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "pbip"
NAME = "BSI_Transporte_EEUU"
DATA_PATH = str(BASE / "data") + "\\"
PBI_THEMES = Path(r"C:\Program Files\Microsoft Power BI Desktop\bin\WebView2Resources\minerva\sharedresources\BaseThemes")
BASE_THEME = "CY26SU02"

# ------------------------------------------------- paleta ATLAS Dark Executive UI
BG = "#0B0E14"        # lienzo
CARD = "#131722"      # tarjetas
LINEA = "#1E293B"     # bordes y grillas
HOVER = "#1A2035"     # relleno al pasar el mouse
NAV = "#0F131C"       # barra de navegación
FILA_ALT = "#161B27"  # filas alternas de tablas
VIOLETA = "#7C4DFF"   # acento ATLAS
CIAN = "#00E5FF"
VERDE = "#00E676"     # bueno (≥80% a tiempo)
AMBAR = "#FFD740"     # neutro (75–80%)
ROJO = "#FF5252"      # malo (<75%)
AZUL_E = "#448AFF"
TXT = "#F8FAFC"       # texto primario
TXT2 = "#94A3B8"      # texto secundario
GRIS_IND = "#64748B"  # promedio de la industria
PALETA = [VIOLETA, CIAN, VERDE, AMBAR, ROJO, AZUL_E, "#B388FF", "#84FFFF", "#69F0AE", "#FFAB40"]
# mapa de calor divergente azul → pizarra → naranja (apto daltónicos, legible sobre fondo oscuro)
CALOR = ["#1D4E89", "#2F6DB5", "#334155", "#8A5A2B", "#C2701E", "#E8590C"]
TEMA_ARCHIVO = "AtlasDarkUI.json"
FONDO_PORTADA = "portada_fondo.png"

# Colores de marca aproximados (referencia visual, no oficiales)
AEROLINEAS = {  # código IATA: (color de marca, color del texto sobre la marca)
    "DL": ("#003366", "#FFFFFF"), "AA": ("#E31837", "#FFFFFF"), "WN": ("#304CB2", "#FFFFFF"),
    "B6": ("#00205B", "#FFFFFF"), "UA": ("#005DAA", "#FFFFFF"), "AS": ("#01426A", "#FFFFFF"),
    "NK": ("#FFEC00", "#0B0E14"), "F9": ("#00843D", "#FFFFFF"), "HA": ("#413691", "#FFFFFF"),
    "OO": ("#1F4E8C", "#FFFFFF"), "YX": ("#2C3E73", "#FFFFFF"), "9E": ("#C8102E", "#FFFFFF"),
    "MQ": ("#0078D2", "#FFFFFF"), "OH": ("#36495A", "#FFFFFF"), "G4": ("#F78F1E", "#0B0E14"),
}

SM = f"{NAME}.SemanticModel"
RP = f"{NAME}.Report"


def gid():
    return str(uuid.uuid4())


def hid(*partes):
    """Identificador estable de 20 caracteres (marcadores, grupos)."""
    return uuid.uuid5(uuid.NAMESPACE_URL, "/".join(partes)).hex[:20]


# =============================================================== MODELO (TMDL)
def col(name, dtype, src=None, hidden=False, fmt=None, summarize="none", category=None, sort_by=None, key=False):
    lines = [f"\tcolumn {q(name)}", f"\t\tdataType: {dtype}"]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    if hidden:
        lines.append("\t\tisHidden")
    if key:
        lines.append("\t\tisKey")
    if category:
        lines.append(f"\t\tdataCategory: {category}")
    lines.append(f"\t\tsummarizeBy: {summarize}")
    lines.append(f"\t\tsourceColumn: {src or name}")
    if sort_by:
        lines.append(f"\t\tsortByColumn: {q(sort_by)}")
    lines.append("")
    return "\n".join(lines)


def q(name):
    import re
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"


def partition(table, m_lines):
    body = "\n".join("\t\t\t\t" + ln for ln in m_lines)
    return f"\tpartition {table} = m\n\t\tmode: import\n\t\tsource =\n{body}\n\n"


def parquet_m(file, extra=None):
    lines = ["let", f'    Origen = Parquet.Document(File.Contents(RutaDatos & "{file}"))']
    last = "Origen"
    for i, step in enumerate(extra or []):
        nm = f"Paso{i+1}"
        lines[-1] += ","
        lines.append(f"    {nm} = {step.replace('{prev}', last)}")
        last = nm
    lines += ["in", f"    {last}"]
    return lines


def measure(name, expr, fmt=None, folder=None, desc=None):
    expr_lines = expr.strip("\n").split("\n")
    if len(expr_lines) == 1:
        head = f"\tmeasure {q(name)} = {expr_lines[0].strip()}"
    else:
        head = f"\tmeasure {q(name)} =\n" + "\n".join("\t\t\t" + ln for ln in expr_lines)
    lines = [head]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    if folder:
        lines.append(f"\t\tdisplayFolder: {folder}")
    if name in IMAGEN_URL:
        lines.append("\t\tdataCategory: ImageUrl")
    lines.append("")
    out = "\n".join(lines)
    if desc:
        out = f"\t/// {desc}\n" + out
    return out


CAUSAS = [("Aerolínea", "DemoraAerolineaMin"), ("Clima", "DemoraClimaMin"), ("Sistema NAS", "DemoraNASMin"),
          ("Seguridad", "DemoraSeguridadMin"), ("Avión previo", "DemoraAvionPrevioMin")]

# Patrón de comparación por índice de mes (dMes[MesIndice] = 1..36), sin depender de tabla de fechas diaria
AA = ("VAR idx = VALUES ( dMes[MesIndice] )\nRETURN\n    IF (\n        MINX ( idx, dMes[MesIndice] ) > 12,\n"
      "        CALCULATE (\n            {m},\n            REMOVEFILTERS ( dMes ),\n"
      "            TREATAS ( SELECTCOLUMNS ( idx, \"i\", dMes[MesIndice] - 12 ), dMes[MesIndice] )\n        )\n    )")

SEMAFORO = f'SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v >= 0.80, "{VERDE}", v >= 0.75, "{AMBAR}", "{ROJO}" )'


def escala(medida, cortes):
    """Color del mapa de calor según 5 cortes (6 tramos de CALOR)."""
    ramas = ", ".join(f'v < {c}, "{CALOR[i]}"' for i, c in enumerate(cortes))
    return f'VAR v = {medida}\nRETURN\n    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), {ramas}, "{CALOR[5]}" )'


MEDIDAS = [
    # --- Volumen
    ("Vuelos", "SUM ( fRutasMes[Vuelos] )", "#,0", "1 Volumen", "Vuelos programados reportados a BTS"),
    ("Vuelos Cancelados", "SUM ( fRutasMes[Cancelados] )", "#,0", "1 Volumen", None),
    ("Vuelos Desviados", "SUM ( fRutasMes[Desviados] )", "#,0", "1 Volumen", None),
    ("Vuelos Operados", "[Vuelos] - [Vuelos Cancelados] - [Vuelos Desviados]", "#,0", "1 Volumen",
     "Vuelos que llegaron a destino (base para puntualidad, criterio BTS)"),
    ("Vuelos Demorados", "SUM ( fRutasMes[LlegadasDemoradas] )", "#,0", "1 Volumen", "Llegadas 15+ min tarde"),
    ("Vuelos a Tiempo", "[Vuelos Operados] - [Vuelos Demorados]", "#,0", "1 Volumen", None),
    ("Millas Voladas", "SUM ( fRutasMes[Millas] )", "#,0", "1 Volumen", None),
    # --- Puntualidad
    ("% A Tiempo", "DIVIDE ( [Vuelos a Tiempo], [Vuelos Operados] )", "0.0%", "2 Puntualidad",
     "Llegadas con menos de 15 min de demora / vuelos operados"),
    ("% Demorados", "DIVIDE ( [Vuelos Demorados], [Vuelos Operados] )", "0.0%", "2 Puntualidad", None),
    ("% Cancelados", "DIVIDE ( [Vuelos Cancelados], [Vuelos] )", "0.00%", "2 Puntualidad", None),
    ("% Desviados", "DIVIDE ( [Vuelos Desviados], [Vuelos] )", "0.00%", "2 Puntualidad", None),
    ("% Salidas Demoradas", "DIVIDE ( SUM ( fRutasMes[SalidasDemoradas] ), [Vuelos] - [Vuelos Cancelados] )", "0.0%",
     "2 Puntualidad", None),
    ("Demora Promedio Llegada", "DIVIDE ( SUM ( fRutasMes[SumaDemoraLlegada] ), SUM ( fRutasMes[NDemoraLlegada] ) )",
     "#,0.0 \"min\"", "2 Puntualidad", "Promedio de todos los vuelos operados (negativo = llegó antes)"),
    ("Demora Promedio Salida", "DIVIDE ( SUM ( fRutasMes[SumaDemoraSalida] ), SUM ( fRutasMes[NDemoraSalida] ) )",
     "#,0.0 \"min\"", "2 Puntualidad", None),
    ("Demora Promedio de Demorados", "DIVIDE ( SUM ( fRutasMes[SumaDemoraDemorados] ), [Vuelos Demorados] )",
     "#,0.0 \"min\"", "2 Puntualidad", "Demora media solo de los vuelos que llegaron 15+ min tarde"),
    ("Taxi Salida Promedio", "DIVIDE ( SUM ( fRutasMes[SumaTaxiSalida] ), SUM ( fRutasMes[NTaxiSalida] ) )",
     "#,0.0 \"min\"", "2 Puntualidad", None),
    # --- Causas
    *[(f"Min Demora {c}", f"SUM ( fRutasMes[{src}] )", "#,0", "3 Causas de demora", None) for c, src in CAUSAS],
    ("Min Demora Total", " + ".join(f"[Min Demora {c}]" for c, _ in CAUSAS), "#,0", "3 Causas de demora",
     "Minutos de demora atribuidos a alguna causa (vuelos 15+ min tarde)"),
    ("Horas de Demora", "DIVIDE ( [Min Demora Total], 60 )", "#,0", "3 Causas de demora", None),
    *[(f"% Causa {c}", f"DIVIDE ( [Min Demora {c}], [Min Demora Total] )", "0.0%", "3 Causas de demora", None)
      for c, _ in CAUSAS],
    ("% Causa Controlable",
     "DIVIDE ( [Min Demora Aerolínea] + [Min Demora Avión previo], [Min Demora Total] )", "0.0%",
     "3 Causas de demora", "Demoras atribuibles a la operación de la aerolínea (propia + avión previo)"),
    # --- Comparaciones
    ("Vuelos Año Anterior", AA.format(m="[Vuelos]"), "#,0", "4 Comparaciones",
     "Mismos meses del año anterior (en blanco si no hay datos)"),
    ("Var % Vuelos vs AA", "DIVIDE ( [Vuelos] - [Vuelos Año Anterior], [Vuelos Año Anterior] )", "+0.0%;-0.0%;0.0%",
     "4 Comparaciones", None),
    ("% A Tiempo Año Anterior", AA.format(m="[% A Tiempo]"), "0.0%", "4 Comparaciones", None),
    ("Δ % A Tiempo vs AA", "IF ( NOT ISBLANK ( [% A Tiempo Año Anterior] ), [% A Tiempo] - [% A Tiempo Año Anterior] )",
     "+0.0%;-0.0%;0.0%", "4 Comparaciones", "Diferencia en puntos porcentuales contra iguales meses del año anterior"),
    ("Δ % A Tiempo 12M",
     "VAR i = MAX ( dMes[MesIndice] )\nVAR ult =\n"
     "    CALCULATE ( [% A Tiempo], REMOVEFILTERS ( dMes ), dMes[MesIndice] > i - 12, dMes[MesIndice] <= i )\n"
     "VAR prev =\n"
     "    CALCULATE ( [% A Tiempo], REMOVEFILTERS ( dMes ), dMes[MesIndice] > i - 24, dMes[MesIndice] <= i - 12 )\n"
     "RETURN\n    IF ( i >= 24 && NOT ISBLANK ( ult ) && NOT ISBLANK ( prev ), ult - prev )",
     "+0.0%;-0.0%;0.0%", "4 Comparaciones",
     "Últimos 12 meses hasta el último mes elegido vs los 12 anteriores (pp)"),
    ("Cancelados por Causa", "VAR v = [Vuelos Cancelados]\nRETURN\n    IF ( v > 0, v )", "#,0", "1 Volumen",
     "Igual que Vuelos Cancelados pero en blanco si es 0 (oculta 'No cancelado')"),
    ("% A Tiempo Mes Anterior",
     "VAR i = MAX ( dMes[MesIndice] )\nRETURN\n    IF (\n        HASONEVALUE ( dMes[MesIndice] ),\n"
     "        CALCULATE ( [% A Tiempo], REMOVEFILTERS ( dMes ), dMes[MesIndice] = i - 1 )\n    )",
     "0.0%", "4 Comparaciones", None),
    ("% A Tiempo Móvil 3M",
     "VAR i = MAX ( dMes[MesIndice] )\nRETURN\n    CALCULATE (\n        [% A Tiempo],\n        REMOVEFILTERS ( dMes ),\n"
     "        dMes[MesIndice] > i - 3,\n        dMes[MesIndice] <= i\n    )",
     "0.0%", "4 Comparaciones", "Últimos 3 meses hasta el mes del contexto"),
    ("Ranking Aerolínea",
     "IF (\n    HASONEVALUE ( dAerolinea[Aerolinea] ),\n    RANKX ( ALLSELECTED ( dAerolinea ), [% A Tiempo], , DESC, DENSE )\n)",
     "0", "4 Comparaciones", "Posición por % a tiempo dentro de lo filtrado"),
    ("Ranking Industria",
     "IF (\n    HASONEVALUE ( dAerolinea[AerolineaCod] ),\n"
     "    RANKX ( FILTER ( ALL ( dAerolinea ), NOT ISBLANK ( [Vuelos] ) ), [% A Tiempo], , DESC, DENSE )\n)",
     "0", "4 Comparaciones", "Posición por % a tiempo entre todas las aerolíneas (ignora el filtro de aerolínea)"),
    ("Aerolíneas con Datos", "COUNTROWS ( FILTER ( ALL ( dAerolinea ), NOT ISBLANK ( [Vuelos] ) ) )", "0",
     "4 Comparaciones", None),
    ("% A Tiempo Industria", "CALCULATE ( [% A Tiempo], REMOVEFILTERS ( dAerolinea ) )", "0.0%", "4 Comparaciones",
     "Promedio de toda la industria EEUU (ignora el filtro de aerolínea)"),
    ("% Cancelados Industria", "CALCULATE ( [% Cancelados], REMOVEFILTERS ( dAerolinea ) )", "0.00%", "4 Comparaciones", None),
    ("Demora Media Industria", "CALCULATE ( [Demora Promedio de Demorados], REMOVEFILTERS ( dAerolinea ) )",
     "#,0.0 \"min\"", "4 Comparaciones", None),
    ("% Controlable Industria", "CALCULATE ( [% Causa Controlable], REMOVEFILTERS ( dAerolinea ) )", "0.0%",
     "4 Comparaciones", None),
    ("Vuelos Promedio por Aerolínea",
     "AVERAGEX ( FILTER ( ALL ( dAerolinea ), NOT ISBLANK ( [Vuelos] ) ), [Vuelos] )", "#,0",
     "4 Comparaciones", "Línea de promedio del cuadrante (eje X)"),
    # --- Patrones (fPatrones: mes × aerolínea × día × hora)
    ("P Vuelos", "SUM ( fPatrones[Vuelos] )", "#,0", "5 Patrones", None),
    ("P % Demorados",
     "DIVIDE (\n    SUM ( fPatrones[LlegadasDemoradas] ),\n"
     "    SUM ( fPatrones[Vuelos] ) - SUM ( fPatrones[Cancelados] ) - SUM ( fPatrones[Desviados] )\n)",
     "0.0%", "5 Patrones", "% de llegadas demoradas según día y hora programada"),
    ("P % A Tiempo", "IF ( NOT ISBLANK ( [P % Demorados] ), 1 - [P % Demorados] )", "0.0%", "5 Patrones", None),
    ("P % Cancelados", "DIVIDE ( SUM ( fPatrones[Cancelados] ), [P Vuelos] )", "0.00%", "5 Patrones", None),
    ("P Demora Media", "DIVIDE ( SUM ( fPatrones[SumaDemoraDemorados] ), SUM ( fPatrones[LlegadasDemoradas] ) )",
     "#,0.0", "5 Patrones", "Demora media (min) de los vuelos demorados según día y hora"),
    # --- Detalle
    ("D Vuelos", "COUNTROWS ( fDetalle )", "#,0", "6 Detalle", None),
    ("Texto Detalle",
     "\"Vuelos de \" & FORMAT ( MAX ( fDetalle[Fecha] ), \"mmmm yyyy\" )",
     None, "6 Detalle", None),
    # --- Formato y textos
    ("Color Puntualidad", f"VAR v = [% A Tiempo]\nRETURN\n    {SEMAFORO}",
     None, "9 Formato", "Semáforo de puntualidad: verde ≥80%, ámbar 75–80%, rojo <75%"),
    ("Color % A Tiempo", "[Color Puntualidad]",
     None, "9 Formato", "Semáforo (alias de Color Puntualidad)"),
    ("Color P % A Tiempo", f"VAR v = [P % A Tiempo]\nRETURN\n    {SEMAFORO}",
     None, "9 Formato", "Semáforo sobre fPatrones: verde ≥80%, ámbar 75–80%, rojo <75%"),
    ("Color % Demorados", escala("[P % Demorados]", [0.12, 0.16, 0.20, 0.24, 0.28]),
     None, "9 Formato", "Mapa de calor: azul = pocas demoras, naranja = muchas"),
    ("Color Heatmap Demora", escala("[P Demora Media]", [66, 70, 72, 75, 78]),
     None, "9 Formato", "Mapa de calor de demora media (min)"),
    ("Color Heatmap Cancelados", escala("[P % Cancelados]", [0.010, 0.013, 0.015, 0.018, 0.021]),
     None, "9 Formato", "Mapa de calor de % cancelados"),
    ("Color Demora Llegada",
     "VAR v = MAX ( fDetalle[DemoraLlegadaMin] )\nRETURN\n"
     "    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v > 60, \"#3B1820\", v <= 0, \"#0E2E22\", BLANK () )",
     None, "9 Formato", "Detalle: rojo si la llegada se demoró más de 60 min, verde si llegó sin demora"),
    ("Texto Período",
     "\"Período: \" & FORMAT ( MIN ( dMes[FechaMes] ), \"mmm yyyy\" ) & \" – \" & FORMAT ( MAX ( dMes[FechaMes] ), \"mmm yyyy\" )",
     None, "9 Formato", None),
    ("Texto Fuente", "\"Fuente: BTS – On-Time Performance (transtats.bts.gov). Elaboración ATLAS.\"", None,
     "9 Formato", None),
    ("Titulo Dinamico",
     "VAR anio = IF ( HASONEVALUE ( dMes[Anio] ), \" \" & VALUES ( dMes[Anio] ), IF ( ISFILTERED ( dMes[Anio] ), \" \" & CONCATENATEX ( VALUES ( dMes[Anio] ), dMes[Anio], \", \", dMes[Anio] ), \"\" ) )\n"
     "VAR mes = IF ( HASONEVALUE ( dMes[Mes] ), \" \" & VALUES ( dMes[Mes] ), IF ( ISFILTERED ( dMes[Mes] ), \" (\" & COUNTROWS ( VALUES ( dMes[Mes] ) ) & \" meses)\", \"\" ) )\n"
     "VAR filtro = TRIM ( anio & mes )\nRETURN\n    \"Resumen de puntualidad\" & IF ( filtro = \"\", \" – todo el período\", \" – \" & filtro )",
     None, "9 Formato", "Título según los filtros de Año y Mes"),
]

# ------------------------------------------------------------ App Shell y portada
SLICER_COLS = ["dMes[Anio]", "dMes[Mes]", "dAerolinea[Aerolinea]", "dAerolinea[TipoAerolinea]", "dOrigen[OrigenEstado]",
               "dOrigen[OrigenCodigo]", "dDestino[DestinoCodigo]", "dCausaCancelacion[CausaCancelacion]",
               "dHora[FranjaHoraria]"]
MEDIDAS += [
    ("Filtros Activos", " + ".join(f"INT ( ISFILTERED ( {c} ) )" for c in SLICER_COLS), "0", "10 App",
     "Cantidad de segmentadores del cajón de filtros con una selección activa"),
    ("Texto Boton Filtros", "\"☰  Filtros (\" & [Filtros Activos] & \")\"", None, "10 App", None),
    ("Portada Vuelos", "FORMAT ( [Vuelos] / 1000000, \"0.0\" ) & \"M\"", None, "10 App", None),
    ("Portada Puntualidad", "FORMAT ( [% A Tiempo], \"0.0%\" )", None, "10 App", None),
    ("Portada Demora", "FORMAT ( [Demora Promedio de Demorados], \"0.0\" ) & \" min\"", None, "10 App", None),
    ("Tooltip Aeropuerto Titulo",
     "SELECTEDVALUE ( dOrigen[OrigenCodigo] ) & \"  ·  \" & SELECTEDVALUE ( dOrigen[OrigenCiudad] ) & \", \" & SELECTEDVALUE ( dOrigen[OrigenEstadoCod] )",
     None, "10 App", None),
    ("Logo Aerolinea", "SELECTEDVALUE ( dAerolinea[Logo_SVG_URL] )", None, "11 SVG", None),
]

# ------------------------------------------------------------------ medidas SVG
# Convenciones: comillas simples dentro del SVG, comillas dobles para strings DAX, números con FORMAT(…, "en-US")
# para que el separador decimal sea el punto, y "%" y "#" codificados como %25 y %23 al final (data URI).
SVG_HEAD = "\"data:image/svg+xml;utf8,\" & SUBSTITUTE ( SUBSTITUTE ( "
SVG_TAIL = ", \"%\", \"%25\" ), \"#\", \"%23\" )"


def n(expr, fmt="0.0"):
    return f"FORMAT ( {expr}, \"{fmt}\", \"en-US\" )"


MEDIDAS += [
    ("KPI_Sparkline_Puntualidad_SVG", f"""
VAR W = 160
VAR H = 36
VAR P = 4
VAR t =
    FILTER (
        ADDCOLUMNS ( ALLSELECTED ( dMes[MesIndice] ), "@v", [% A Tiempo] ),
        NOT ISBLANK ( [@v] )
    )
VAR mn = MINX ( t, [@v] )
VAR mx = MAXX ( t, [@v] )
VAR i0 = MINX ( t, dMes[MesIndice] )
VAR i1 = MAXX ( t, dMes[MesIndice] )
VAR pts =
    ADDCOLUMNS (
        t,
        "@x", P + DIVIDE ( dMes[MesIndice] - i0, i1 - i0 ) * ( W - 2 * P ),
        "@y", H - P - DIVIDE ( [@v] - mn, mx - mn ) * ( H - 2 * P )
    )
VAR linea = CONCATENATEX ( pts, {n("[@x]")} & "," & {n("[@y]")}, " ", dMes[MesIndice], ASC )
VAR ux = MAXX ( FILTER ( pts, dMes[MesIndice] = i1 ), [@x] )
VAR uy = MAXX ( FILTER ( pts, dMes[MesIndice] = i1 ), [@y] )
VAR svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='160' height='36' viewBox='0 0 160 36'>"
        & "<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>"
        & "<stop offset='0' stop-color='{CIAN}' stop-opacity='0.45'/><stop offset='1' stop-color='{CIAN}' stop-opacity='0'/>"
        & "</linearGradient></defs>"
        & "<polygon points='" & P & "," & H & " " & linea & " " & {n("ux")} & "," & H & "' fill='url(#g)'/>"
        & "<polyline points='" & linea & "' fill='none' stroke='{CIAN}' stroke-width='1.6' stroke-linejoin='round'/>"
        & "<circle cx='" & {n("ux")} & "' cy='" & {n("uy")} & "' r='5' fill='{CIAN}' opacity='0.25'/>"
        & "<circle cx='" & {n("ux")} & "' cy='" & {n("uy")} & "' r='2.6' fill='{CIAN}'/>"
        & "</svg>"
RETURN
    IF ( COUNTROWS ( t ) >= 2, {SVG_HEAD}svg{SVG_TAIL} )""",
     None, "11 SVG", "Mini área de la evolución mensual del % a tiempo (160×36)"),
    ("KPI_Bullet_Meta_SVG", f"""
VAR v = [% A Tiempo]
VAR lo = 0.60
VAR hi = 0.95
VAR x = MIN ( MAX ( DIVIDE ( v - lo, hi - lo ), 0.02 ), 1 ) * 160
VAR xm = DIVIDE ( 0.80 - lo, hi - lo ) * 160
VAR col = SWITCH ( TRUE (), v >= 0.80, "{VERDE}", v >= 0.75, "{AMBAR}", "{ROJO}" )
VAR svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='160' height='14' viewBox='0 0 160 14'>"
        & "<rect x='0' y='3' width='160' height='8' rx='4' fill='{LINEA}'/>"
        & "<rect x='0' y='3' width='" & {n("x")} & "' height='8' rx='4' fill='" & col & "'/>"
        & "<rect x='" & {n("xm - 1")} & "' y='0' width='2' height='14' fill='#FFFFFF'/>"
        & "</svg>"
RETURN
    IF ( NOT ISBLANK ( v ), {SVG_HEAD}svg{SVG_TAIL} )""",
     None, "11 SVG", "Barra de progreso del % a tiempo contra la meta de 80% (escala 60–95%)"),
    ("Tabla_Barra_Puntualidad_SVG", f"""
VAR v = [% A Tiempo]
VAR w = MIN ( MAX ( DIVIDE ( v - 0.60, 0.35 ), 0.03 ), 1 ) * 84
VAR col = SWITCH ( TRUE (), v >= 0.80, "{VERDE}", v >= 0.75, "{AMBAR}", "{ROJO}" )
VAR svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='130' height='18' viewBox='0 0 130 18'>"
        & "<defs><linearGradient id='b' x1='0' y1='0' x2='1' y2='0'>"
        & "<stop offset='0' stop-color='" & col & "' stop-opacity='0.25'/><stop offset='1' stop-color='" & col & "'/>"
        & "</linearGradient></defs>"
        & "<rect x='0' y='4' width='84' height='10' rx='5' fill='{LINEA}'/>"
        & "<rect x='0' y='4' width='" & {n("w")} & "' height='10' rx='5' fill='url(#b)'/>"
        & "<text x='128' y='13' text-anchor='end' font-family='Segoe UI' font-size='11' font-weight='600' fill='{TXT}'>"
        & FORMAT ( v, "0.0%" ) & "</text></svg>"
RETURN
    IF ( NOT ISBLANK ( v ), {SVG_HEAD}svg{SVG_TAIL} )""",
     None, "11 SVG", "Barra del % a tiempo con semáforo (escala 60–95%) para tablas"),
    ("Tabla_Badge_Variacion_SVG", f"""
VAR d = [Δ % A Tiempo 12M]
VAR pp = d * 100
VAR sube = pp >= 0
VAR col = IF ( sube, "{VERDE}", "{ROJO}" )
VAR rgb = IF ( sube, "0,230,118", "255,82,82" )
VAR txt = IF ( sube, "▲ +", "▼ " ) & FORMAT ( pp, "0.0" ) & " pp"
VAR svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='85' height='22' viewBox='0 0 85 22'>"
        & "<rect x='0.5' y='0.5' width='84' height='21' rx='10.5' fill='rgba(" & rgb & ",0.14)' stroke='" & col & "' stroke-width='0.8'/>"
        & "<text x='42.5' y='15' text-anchor='middle' font-family='Segoe UI' font-size='11' font-weight='600' fill='" & col & "'>"
        & txt & "</text></svg>"
RETURN
    IF ( NOT ISBLANK ( d ), {SVG_HEAD}svg{SVG_TAIL} )""",
     None, "11 SVG", "Etiqueta ▲/▼ con la variación del % a tiempo en los últimos 12 meses (pp)"),
    ("Vuelo_Estado_Badge_SVG", f"""
VAR canc = MAX ( fDetalle[Cancelado] )
VAR desv = MAX ( fDetalle[Desviado] )
VAR d = MAX ( fDetalle[DemoraLlegadaMin] )
VAR causa = UPPER ( SELECTEDVALUE ( dCausaCancelacion[CausaCancelacion] ) )
VAR estado =
    SWITCH (
        TRUE (),
        canc = 1, "✕ CANCELADO · " & causa,
        desv = 1, "↷ DESVIADO",
        d > 60, "▲ DEMORA >60M",
        d >= 15, "▲ DEMORA 15–60M",
        "● A TIEMPO"
    )
VAR col = SWITCH ( TRUE (), canc = 1, "{ROJO}", desv = 1, "{AZUL_E}", d > 60, "{ROJO}", d >= 15, "{AMBAR}", "{VERDE}" )
VAR rgb = SWITCH ( TRUE (), canc = 1, "255,82,82", desv = 1, "68,138,255", d > 60, "255,82,82", d >= 15, "255,215,64", "0,230,118" )
VAR svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='150' height='22' viewBox='0 0 150 22'>"
        & "<rect x='0.5' y='0.5' width='149' height='21' rx='10.5' fill='rgba(" & rgb & ",0.14)' stroke='" & col & "' stroke-width='0.8'/>"
        & "<text x='10' y='15' font-family='Segoe UI' font-size='10' font-weight='600' fill='" & col & "'>"
        & estado & "</text></svg>"
RETURN
    IF ( COUNTROWS ( fDetalle ) = 1, {SVG_HEAD}svg{SVG_TAIL} )""",
     None, "11 SVG", "Estado del vuelo: a tiempo, demorado, demora >60 min, desviado o cancelado (con causa)"),
    ("Tooltip_Top3_Rutas_SVG", f"""
VAR t =
    TOPN (
        3,
        FILTER (
            ADDCOLUMNS ( VALUES ( dDestino[DestinoCodigo] ), "@v", [Vuelos], "@p", [% Demorados] ),
            [@v] >= 300 && NOT ISBLANK ( [@p] )
        ),
        [@p], DESC
    )
VAR mx = MAXX ( t, [@p] )
VAR r = ADDCOLUMNS ( t, "@r", RANKX ( t, [@p], , DESC ) )
VAR o = SELECTEDVALUE ( dOrigen[OrigenCodigo] )
VAR filas =
    CONCATENATEX (
        r,
        VAR y = ( [@r] - 1 ) * 30
        RETURN
            "<g transform='translate(0," & y & ")'>"
                & "<text x='0' y='15' font-family='Segoe UI' font-size='11' font-weight='600' fill='{TXT}'>" & o & " → " & dDestino[DestinoCodigo] & "</text>"
                & "<rect x='86' y='5' width='140' height='12' rx='6' fill='{LINEA}'/>"
                & "<rect x='86' y='5' width='" & {n("DIVIDE ( [@p], mx ) * 140")} & "' height='12' rx='6' fill='{ROJO}'/>"
                & "<text x='292' y='15' text-anchor='end' font-family='Segoe UI' font-size='11' fill='{TXT2}'>" & FORMAT ( [@p], "0.0%" ) & "</text>"
                & "</g>",
        "",
        [@r], ASC
    )
VAR svg = "<svg xmlns='http://www.w3.org/2000/svg' width='300' height='90' viewBox='0 0 300 90'>" & filas & "</svg>"
RETURN
    IF ( NOT ISEMPTY ( t ), {SVG_HEAD}svg{SVG_TAIL} )""",
     None, "11 SVG", "Top 3 rutas con más % de demoras desde el aeropuerto (rutas con 300+ vuelos)"),
]


def hero_kpi(i, etiqueta, actual, industria, fmt, mejor_alto, unidad):
    """Mosaico KPI del perfil de aerolínea: valor + diferencia contra la industria."""
    x, y = 16 + (i % 2) * 192, 112 + (i // 2) * 76
    dif = f"( {actual} - {industria} )"
    if unidad == "pp":
        txt_dif = f"FORMAT ( ABS ( {dif} ) * 100, \"0.0\" ) & \" pp\""
    else:
        txt_dif = f"FORMAT ( ABS ( {dif} ), \"0.0\" ) & \" min\""
    bueno = f"( {dif} >= 0 )" if mejor_alto else f"( {dif} <= 0 )"
    return f"""
VAR k{i}v = {actual}
VAR k{i}d =
    IF (
        sel && NOT ISBLANK ( k{i}v ),
        "<text x='{x + 12}' y='{y + 62}' font-family='Segoe UI' font-size='10' font-weight='600' fill='"
            & IF ( {bueno}, "{VERDE}", "{ROJO}" ) & "'>"
            & IF ( {dif} >= 0, "▲ ", "▼ " ) & {txt_dif} & " vs industria</text>",
        "<text x='{x + 12}' y='{y + 62}' font-family='Segoe UI' font-size='10' fill='{TXT2}'>Promedio EEUU</text>"
    )
VAR k{i} =
    "<rect x='{x}' y='{y}' width='180' height='68' rx='10' fill='{BG}' stroke='{LINEA}'/>"
        & "<text x='{x + 12}' y='{y + 20}' font-family='Segoe UI' font-size='10' fill='{TXT2}'>{etiqueta}</text>"
        & "<text x='{x + 12}' y='{y + 44}' font-family='Segoe UI' font-size='20' font-weight='700' fill='{TXT}'>"
        & FORMAT ( k{i}v, "{fmt}" ) & "</text>"
        & k{i}d"""


HERO_KPIS = [("% A TIEMPO", "[% A Tiempo]", "[% A Tiempo Industria]", "0.0%", True, "pp"),
             ("% CANCELADOS", "[% Cancelados]", "[% Cancelados Industria]", "0.00%", False, "pp"),
             ("DEMORA MEDIA (DEMORADOS)", "[Demora Promedio de Demorados]", "[Demora Media Industria]", '0.0 ""min""', False, "min"),
             ("% DEMORA CONTROLABLE", "[% Causa Controlable]", "[% Controlable Industria]", "0.0%", False, "pp")]

MEDIDAS.append(("Benchmark_Hero_SVG", f"""
VAR sel = HASONEVALUE ( dAerolinea[AerolineaCod] )
VAR cod = IF ( sel, SELECTEDVALUE ( dAerolinea[AerolineaCod] ), "US" )
VAR nombre = IF ( sel, SELECTEDVALUE ( dAerolinea[Aerolinea] ), "Industria EEUU" )
VAR tipo = IF ( sel, UPPER ( SELECTEDVALUE ( dAerolinea[TipoAerolinea] ) ), "PROMEDIO DE " & [Aerolíneas con Datos] & " AEROLÍNEAS" )
VAR marca = IF ( sel, SELECTEDVALUE ( dAerolinea[Color_Marca] ), "{VIOLETA}" )
VAR fg = IF ( sel, SELECTEDVALUE ( dAerolinea[Color_Texto] ), "#FFFFFF" )
VAR rk =
    IF (
        sel,
        "#" & [Ranking Industria] & " de " & [Aerolíneas con Datos] & " en puntualidad",
        "Elegí una aerolínea arriba para compararla"
    ){"".join(hero_kpi(i, *k) for i, k in enumerate(HERO_KPIS))}
VAR svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='268' viewBox='0 0 400 268'>"
        & "<rect x='16' y='16' width='72' height='72' rx='14' fill='" & marca & "'/>"
        & "<path d='M30 62 L74 40 L62 62 Z' fill='" & fg & "' opacity='0.9'/>"
        & "<text x='52' y='38' text-anchor='middle' font-family='Segoe UI' font-size='15' font-weight='800' fill='" & fg & "'>" & cod & "</text>"
        & "<text x='104' y='42' font-family='Segoe UI' font-size='19' font-weight='700' fill='{TXT}'>" & nombre & "</text>"
        & "<rect x='104' y='52' width='" & {n("LEN ( tipo ) * 6.6 + 18")} & "' height='18' rx='9' fill='rgba(124,77,255,0.18)' stroke='{VIOLETA}' stroke-width='0.8'/>"
        & "<text x='113' y='65' font-family='Segoe UI' font-size='9.5' font-weight='600' fill='#B9A6FF'>" & tipo & "</text>"
        & "<text x='104' y='90' font-family='Segoe UI' font-size='11' fill='{CIAN}'>" & rk & "</text>"
        & k0 & k1 & k2 & k3
        & "</svg>"
RETURN
    {SVG_HEAD}svg{SVG_TAIL}""", None, "11 SVG",
    "Tarjeta de perfil: insignia, segmento, ranking y 4 KPIs contra el promedio de la industria"))

MEDIDAS.append(("Selector_Aerolinea_SVG", f"""
VAR cod = SELECTEDVALUE ( dAerolinea[AerolineaCod] )
VAR c = SELECTEDVALUE ( dAerolinea[Color_Marca] )
VAR fg = SELECTEDVALUE ( dAerolinea[Color_Texto] )
VAR v = [% A Tiempo]
VAR col = SWITCH ( TRUE (), v >= 0.80, "{VERDE}", v >= 0.75, "{AMBAR}", "{ROJO}" )
VAR svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='80' height='64' viewBox='0 0 80 64'>"
        & "<rect x='8' y='8' width='22' height='22' rx='6' fill='" & c & "'/>"
        & "<path d='M11 25 L27 17 L23 25 Z' fill='" & fg & "' opacity='0.92'/>"
        & "<text x='35' y='26' font-family='Segoe UI' font-size='15' font-weight='800' fill='{TXT}'>" & cod & "</text>"
        & "<rect x='8' y='40' width='64' height='4' rx='2' fill='{LINEA}'/>"
        & "<rect x='8' y='40' width='" & {n("MIN ( MAX ( DIVIDE ( v - 0.60, 0.35 ), 0.05 ), 1 ) * 64")} & "' height='4' rx='2' fill='" & col & "'/>"
        & "<text x='8' y='58' font-family='Segoe UI' font-size='10' font-weight='600' fill='" & col & "'>" & FORMAT ( v, "0.0%" ) & "</text>"
        & "</svg>"
RETURN
    IF ( NOT ISBLANK ( cod ), {SVG_HEAD}svg{SVG_TAIL} )""", None, "11 SVG",
    "Mosaico del selector de aerolíneas: insignia + % a tiempo con semáforo"))

IMAGEN_URL = {m[0] for m in MEDIDAS if m[0].endswith("_SVG")} | {"Logo Aerolinea"}

# Insignia IATA (columna calculada): emblema propio, no imita logos oficiales
LOGO_SVG = f"""
VAR c = dAerolinea[Color_Marca]
VAR fg = dAerolinea[Color_Texto]
VAR cod = dAerolinea[AerolineaCod]
VAR nom = UPPER ( LEFT ( dAerolinea[Aerolinea], SEARCH ( " ", dAerolinea[Aerolinea] & " " ) - 1 ) )
VAR svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='120' height='36' viewBox='0 0 120 36'>"
        & "<rect x='0.5' y='0.5' width='119' height='35' rx='8' fill='{CARD}' stroke='" & c & "' stroke-width='1'/>"
        & "<rect x='0' y='0' width='36' height='36' rx='8' fill='" & c & "'/>"
        & "<path d='M7 25 L29 14 L23 25 Z' fill='" & fg & "' opacity='0.92'/>"
        & "<circle cx='27' cy='10' r='2.2' fill='" & fg & "' opacity='0.6'/>"
        & "<text x='44' y='18' font-family='Segoe UI' font-size='15' font-weight='800' fill='{TXT}'>" & cod & "</text>"
        & "<text x='44' y='29' font-family='Segoe UI' font-size='7.5' font-weight='600' letter-spacing='0.6' fill='{TXT2}'>" & nom & "</text>"
        & "</svg>"
RETURN
    {SVG_HEAD}svg{SVG_TAIL}"""


def calc_col(name, expr, dtype="string", category=None, hidden=False):
    lines = expr.strip("\n").split("\n")
    head = (f"\tcolumn {q(name)} = {lines[0].strip()}" if len(lines) == 1 else
            f"\tcolumn {q(name)} =\n" + "\n".join("\t\t\t" + ln for ln in lines))
    out = [head, f"\t\tdataType: {dtype}"]
    if hidden:
        out.append("\t\tisHidden")
    if category:
        out.append(f"\t\tdataCategory: {category}")
    out += ["\t\tsummarizeBy: none", ""]
    return "\n".join(out)


def tmdl_aerolinea():
    sw = lambda i: "SWITCH ( dAerolinea[AerolineaCod], " + ", ".join(
        f'"{k}", "{v[i]}"' for k, v in AEROLINEAS.items()) + f', "{VIOLETA if i == 0 else "#FFFFFF"}" )'
    base = tabla("dAerolinea", [("AerolineaCod", "string", {"key": True}), ("Aerolinea", "string"),
                                ("TipoAerolinea", "string")], "dAerolinea.parquet")
    extra = "\n".join([calc_col("Color_Marca", sw(0)), calc_col("Color_Texto", sw(1), hidden=True),
                       calc_col("Logo_SVG_URL", LOGO_SVG, category="ImageUrl")])
    i = base.index("\tpartition ")
    return base[:i] + extra + "\n" + base[i:]


FP = "Selector_Metrica_Heatmap"
METRICAS_HEATMAP = [("% vuelos demorados", "P % Demorados", "Color % Demorados"),
                    ("Demora media (min)", "P Demora Media", "Color Heatmap Demora"),
                    ("% cancelados", "P % Cancelados", "Color Heatmap Cancelados")]


def tmdl_parametro():
    filas = ",\n".join(f"\t\t\t\t    (\"{e}\", NAMEOF ( 'Medidas'[{m}] ), {i})" for i, (e, m, _) in enumerate(METRICAS_HEATMAP))
    return f"""table {FP}

\tcolumn {FP}
\t\tdataType: string
\t\tsummarizeBy: none
\t\tsourceColumn: [Value1]
\t\tsortByColumn: '{FP} Orden'

\t\trelatedColumnDetails
\t\t\tgroupByColumn: '{FP} Campos'

\tcolumn '{FP} Campos'
\t\tdataType: string
\t\tisHidden
\t\tsummarizeBy: none
\t\tsourceColumn: [Value2]
\t\tsortByColumn: '{FP} Orden'

\t\textendedProperty ParameterMetadata =
\t\t\t\t{{
\t\t\t\t  "version": 3,
\t\t\t\t  "kind": 2
\t\t\t\t}}

\tcolumn '{FP} Orden'
\t\tdataType: int64
\t\tisHidden
\t\tsummarizeBy: sum
\t\tsourceColumn: [Value3]

\tpartition {FP} = calculated
\t\tmode: import
\t\tsource =
\t\t\t\t{{
{filas}
\t\t\t\t}}

"""


def tabla(nombre, columnas, archivo, extra_m=None, header=None):
    s = [f"table {nombre}", *(header or []), ""]
    s += [col(*c[:2], **(c[2] if len(c) > 2 else {})) for c in columnas]
    s.append(partition(nombre, parquet_m(archivo, extra_m)))
    return "\n".join(s)


H = {"hidden": True, "fmt": "0"}
NUM = {"summarize": "sum", "hidden": True}

TABLAS_DEF = {
    "Medidas": None,  # tabla de medidas (se arma aparte)
    "fRutasMes": ([("MesKey", "int64", H), ("AerolineaCod", "string", {"hidden": True}),
                   ("OrigenCod", "string", {"hidden": True}), ("DestinoCod", "string", {"hidden": True}),
                   ("CodigoCancelacion", "string", {"hidden": True}),
                   *[(c, "int64", NUM) for c in ["Vuelos", "Cancelados", "Desviados", "LlegadasDemoradas",
                                                 "SalidasDemoradas", "NDemoraLlegada", "NDemoraSalida", "NTaxiSalida"]],
                   *[(c, "double", NUM) for c in ["SumaDemoraLlegada", "SumaDemoraDemorados", "SumaDemoraSalida",
                                                  "SumaTaxiSalida", "Millas"] + [s for _, s in CAUSAS]]],
                  "fRutasMes.parquet"),
    "fPatrones": ([("MesKey", "int64", H), ("AerolineaCod", "string", {"hidden": True}),
                   ("DiaSemanaNum", "int64", H), ("HoraProgramada", "int64", H),
                   *[(c, "int64", NUM) for c in ["Vuelos", "Cancelados", "Desviados", "LlegadasDemoradas"]],
                   ("SumaDemoraDemorados", "double", NUM)],
                  "fPatrones.parquet"),
    "fDetalle": ([("Fecha", "dateTime", {"fmt": "dd/mm/yyyy"}), ("MesKey", "int64", H),
                  ("AerolineaCod", "string", {"hidden": True}), ("NroVuelo", "int64", {"fmt": "0"}),
                  ("OrigenCod", "string", {"hidden": True}), ("DestinoCod", "string", {"hidden": True}),
                  ("Ruta", "string"), ("HoraProgramada", "int64", H),
                  ("DemoraSalidaMin", "double", {"fmt": "0"}), ("DemoraLlegadaMin", "double", {"fmt": "0"}),
                  ("Cancelado", "int64", {"fmt": "0"}), ("CodigoCancelacion", "string", {"hidden": True}),
                  ("Desviado", "int64", {"fmt": "0"}), ("DistanciaMillas", "double", {"fmt": "#,0"})],
                 "fDetalle.parquet", ["Table.TransformColumnTypes({prev}, {{\"Fecha\", type date}})"]),
    "dMes": ([("MesKey", "int64", {**H, "key": True}), ("FechaMes", "dateTime", {"fmt": "mmm yyyy"}),
              ("Anio", "int64", {"fmt": "0"}), ("MesNum", "int64", H), ("Mes", "string", {"sort_by": "MesNum"}),
              ("AnioMes", "string", {"sort_by": "MesIndice"}), ("MesIndice", "int64", H), ("Trimestre", "string"), ("Temporada", "string")],
             "dMes.parquet", ["Table.TransformColumnTypes({prev}, {{\"FechaMes\", type date}})"]),
    "dAerolinea": None,  # con columnas calculadas (se arma aparte)
    "dOrigen": None, "dDestino": None,
    "dDiaSemana": ([("DiaSemanaNum", "int64", {**H, "key": True}), ("DiaSemana", "string", {"sort_by": "DiaSemanaNum"})],
                   "dDiaSemana.parquet"),
    "dHora": ([("HoraProgramada", "int64", {"fmt": "0", "key": True}), ("HoraTexto", "string"),
               ("FranjaOrden", "int64", H), ("FranjaHoraria", "string", {"sort_by": "FranjaOrden"})], "dHora.parquet"),
    "dCausaCancelacion": ([("CodigoCancelacion", "string", {"key": True, "hidden": True}),
                           ("CausaCancelacion", "string")], "dCausaCancelacion.parquet"),
    FP: None,  # parámetro de campo (tabla calculada)
}
TABLAS = list(TABLAS_DEF)
TABLAS_M = [t for t in TABLAS if t != FP]  # tablas con consulta Power Query

RELS = [
    *[(f"{f}.MesKey", "dMes.MesKey") for f in ("fRutasMes", "fPatrones", "fDetalle")],
    *[(f"{f}.AerolineaCod", "dAerolinea.AerolineaCod") for f in ("fRutasMes", "fPatrones", "fDetalle")],
    *[(f"{f}.OrigenCod", "dOrigen.OrigenCodigo") for f in ("fRutasMes", "fDetalle")],
    *[(f"{f}.DestinoCod", "dDestino.DestinoCodigo") for f in ("fRutasMes", "fDetalle")],
    *[(f"{f}.CodigoCancelacion", "dCausaCancelacion.CodigoCancelacion") for f in ("fRutasMes", "fDetalle")],
    *[(f"{f}.HoraProgramada", "dHora.HoraProgramada") for f in ("fPatrones", "fDetalle")],
    ("fPatrones.DiaSemanaNum", "dDiaSemana.DiaSemanaNum"),
]


def tmdl_medidas():
    s = ["table Medidas", ""]
    s += [measure(n_, e, f, d, desc) for n_, e, f, d, desc in MEDIDAS]
    s.append(col("Columna", "int64", hidden=True))
    s.append(partition("Medidas", ["let", '    Origen = #table(type table [Columna = Int64.Type], {})', "in", "    Origen"]))
    return "\n".join(s)


def tmdl_aeropuerto(rol):
    t = f"d{rol}"
    return tabla(t, [
        (f"{rol}Codigo", "string", {"key": True}),
        (f"{rol}Ciudad", "string", {"category": "City"}),
        (f"{rol}EstadoCod", "string"),
        (f"{rol}Estado", "string", {"category": "StateOrProvince"}),
        (f"{rol}NombreAeropuerto", "string"),
        (f"{rol}Latitud", "double", {"category": "Latitude", "fmt": "0.0000"}),
        (f"{rol}Longitud", "double", {"category": "Longitude", "fmt": "0.0000"}),
    ], "dAeropuerto.parquet", [f"Table.TransformColumnNames({{prev}}, each \"{rol}\" & _)"])


def escribir_modelo():
    d = OUT / SM / "definition"
    (d / "tables").mkdir(parents=True, exist_ok=True)
    w(OUT / SM / "definition.pbism", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2))
    w(d / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    model = ["model Model", "\tculture: es-ES", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tdiscourageImplicitMeasures", "\tsourceQueryCulture: es-AR", "\tdataAccessOptions",
             "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull",
             "", "annotation __PBI_TimeIntelligenceEnabled = 0", "",
             f"annotation PBI_QueryOrder = {json.dumps(['RutaDatos'] + TABLAS_M, ensure_ascii=False)}", ""]
    model += [f"ref table {t}" for t in TABLAS]
    w(d / "model.tmdl", "\n".join(model) + "\n")
    w(d / "expressions.tmdl",
      f'expression RutaDatos = "{DATA_PATH}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
      "\tannotation PBI_ResultType = Text\n")
    rel = []
    for f, t in RELS:
        rel += [f"relationship {uuid.uuid5(uuid.NAMESPACE_URL, f + t)}", f"\tfromColumn: {f}", f"\ttoColumn: {t}", ""]
    w(d / "relationships.tmdl", "\n".join(rel))
    for t, spec in TABLAS_DEF.items():
        if t == "Medidas":
            txt = tmdl_medidas()
        elif t == "dAerolinea":
            txt = tmdl_aerolinea()
        elif t == FP:
            txt = tmdl_parametro()
        elif t in ("dOrigen", "dDestino"):
            txt = tmdl_aeropuerto(t[1:])
        else:
            txt = tabla(t, *spec)
        w(d / "tables" / f"{t}.tmdl", txt)


# =============================================================== REPORTE (PBIR)
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
VC_SCHEMA = f"{SCH}/visualContainer/2.4.0/schema.json"

ETIQ_CAUSA = {"Aerolínea": "Operación aerolínea", "Clima": "Clima", "Sistema NAS": "Sistema NAS",
              "Seguridad": "Seguridad", "Avión previo": "Avión previo"}

# Nombres visibles en ejes, leyendas y encabezados de tabla
NOMBRES = {
    "AnioMes": "Mes", "Anio": "Año", "Aerolinea": "Aerolínea", "TipoAerolinea": "Tipo",
    "OrigenCodigo": "Origen", "OrigenCiudad": "Ciudad", "OrigenEstadoCod": "Estado",
    "DestinoCodigo": "Destino", "HoraTexto": "Hora", "FranjaHoraria": "Franja horaria", "DiaSemana": "Día",
    "CausaCancelacion": "Causa de cancelación", "NroVuelo": "Vuelo", "DemoraSalidaMin": "Demora salida (min)",
    "DemoraLlegadaMin": "Demora llegada (min)", "DistanciaMillas": "Millas",
    "P % A Tiempo": "% a tiempo", "P % Demorados": "% demorados", "P % Cancelados": "% cancelados",
    "% A Tiempo": "% a tiempo", "% A Tiempo Móvil 3M": "Promedio móvil 3 meses", "% Cancelados": "% cancelados",
    "Δ % A Tiempo vs AA": "Δ vs año ant. (pp)", "Demora Promedio de Demorados": "Demora media",
    "% Causa Controlable": "% controlable", "Ranking Aerolínea": "Ranking", "Taxi Salida Promedio": "Taxi salida (min)",
    "Vuelos Demorados": "Vuelos demorados", "Vuelos Cancelados": "Vuelos cancelados",
    "Demora Promedio Llegada": "Demora media llegada",
    **{f"Min Demora {c}": ETIQ_CAUSA[c] for c, _ in CAUSAS}, **{f"% Causa {c}": ETIQ_CAUSA[c] for c, _ in CAUSAS},
    "Δ % A Tiempo 12M": "Δ 12M (pp)", "Cancelados por Causa": "Vuelos cancelados", "FechaMes": "Mes",
    "Ranking Industria": "#", "Logo_SVG_URL": "Logo", "AerolineaCod": "IATA",
    "Tabla_Barra_Puntualidad_SVG": "% a tiempo", "Tabla_Badge_Variacion_SVG": "Δ 12M",
    "Vuelo_Estado_Badge_SVG": "Estado", "% A Tiempo Industria": "Promedio industria EEUU",
    "Benchmark_Hero_SVG": " ", "Tooltip_Top3_Rutas_SVG": " ", "P Demora Media": "Demora media (min)",
}


def _nombre(d, prop):
    if prop in NOMBRES:
        d["displayName"] = NOMBRES[prop]
        d["nativeQueryRef"] = NOMBRES[prop]
    return d


def C(entity, prop):  # columna
    return _nombre({"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
                    "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}, prop)


def PROM(entity, prop):  # columna agregada como promedio (lat/long en mapas Azure)
    col_ = {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
    return {"field": {"Aggregation": {"Expression": col_, "Function": 1}},
            "queryRef": f"Avg({entity}.{prop})", "nativeQueryRef": f"Promedio de {prop}"}


def M(prop, entity="Medidas"):  # medida
    return _nombre({"field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
                    "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}, prop)


def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": f"'{v}'"}}}


def color(c):
    return {"solid": {"color": lit(c)}}


def color_medida(medida):
    return {"solid": {"color": {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": medida}}}}}


def expr_medida(medida):
    return {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": medida}}}


def titulo(texto):
    return {"title": [{"properties": {"show": lit(True), "text": lit(texto), "fontColor": color(TXT),
                                      "fontSize": lit(11), "bold": lit(True)}}]}


SIN_TARJETA = {"background": [{"properties": {"show": lit(False)}}], "border": [{"properties": {"show": lit(False)}}],
               "dropShadow": [{"properties": {"show": lit(False)}}],
               "padding": [{"properties": {"top": lit(0), "bottom": lit(0), "left": lit(0), "right": lit(0)}}]}


def contenedor(extra=None, pad=16):
    o = {"background": [{"properties": {"show": lit(True), "color": color(CARD)}}],
         "border": [{"properties": {"show": lit(True), "color": color(LINEA), "radius": lit(12)}}],
         "dropShadow": [{"properties": {"show": lit(False)}}],
         "padding": [{"properties": {"top": lit(pad), "bottom": lit(pad), "left": lit(pad), "right": lit(pad)}}]}
    if extra:
        o.update(extra)
    return o


GRAFICOS = {"lineChart", "clusteredBarChart", "clusteredColumnChart", "columnChart", "barChart",
            "hundredPercentStackedBarChart", "scatterChart"}
BARRAS = {"clusteredBarChart", "clusteredColumnChart"}
MAPA_ZOOM = {"p1resumen": 2.3, "p3aeropuertos": 3.2}

# Cuerpo de las páginas de análisis: antes iba de y=136 a y=690 (debajo de la fila de segmentadores);
# ahora arranca en y=56, debajo de la barra de navegación de 48 px.
Y0_VIEJO, Y0, Y1 = 136, 56, 688
K = (Y1 - Y0) / (690 - Y0_VIEJO)

PAGINAS_APP = [  # (nombre interno, pestaña, etiqueta de la píldora, título del lanzador, descripción)
    ("p1resumen", "Resumen", "Resumen", "Resumen Ejecutivo", "Visión global y tendencias"),
    ("p2aerolineas", "Comparativo", "Comparativo", "Comparativo General", "Panorama de aerolíneas"),
    ("p7benchmark", "Benchmark", "Benchmark", "Benchmark de Aerolíneas", "Análisis con logos y duelo vs. industria"),
    ("p3aeropuertos", "Aeropuertos y rutas", "Aeropuertos", "Aeropuertos y Rutas", "Mapa geoespacial y corredores"),
    ("p4causas", "Causas de demora", "Causas", "Causas de Demora", "Atribución y factores controlables"),
    ("p5patrones", "Patrones horarios", "Patrones", "Patrones Horarios", "Matriz térmica día/hora"),
    ("p6detalle", "Detalle de vuelos", "Detalle", "Detalle de Vuelos", "Consulta granular vuelo por vuelo"),
]


def boton(nombre, x, y, wd, h, z, texto, accion=None, fill=None, fill_t=100, texto_color=TXT2, hover_fill=HOVER,
          hover_t=0, hover_texto=TXT, borde=None, hover_borde=None, radio=14, tam=10, negrita=True, alinear="center",
          texto_medida=None, padre=None, oculto=False):
    """Botón (actionButton) con estados Normal y Al mantener el puntero."""
    con_borde = borde is not None or hover_borde is not None

    def estado(sel, fc, ft, tc, bc):
        return (
            {"properties": {"fillColor": color(fc or BG), "transparency": lit(ft)}, "selector": {"id": sel}},
            {"properties": {"fontColor": color(tc)}, "selector": {"id": sel}},
            {"properties": {"lineColor": color(bc or BG), "transparency": lit(0 if bc else 100), "weight": lit(1),
                            "roundEdge": lit(radio)}, "selector": {"id": sel}},
        )
    d, hv = estado("default", fill, fill_t, texto_color, borde), estado("hover", hover_fill, hover_t, hover_texto,
                                                                         hover_borde or borde)
    txt = {"text": expr_medida(texto_medida) if texto_medida else lit(texto), "fontSize": lit(tam),
           "fontFamily": lit("Segoe UI Semibold" if negrita else "Segoe UI"), "horizontalAlignment": lit(alinear),
           "verticalAlignment": lit("middle"), "fontColor": color(texto_color)}
    objects = {
        "icon": [{"properties": {"show": lit(False)}}],
        "text": [{"properties": {"show": lit(bool(texto or texto_medida))}},
                 {"properties": txt, "selector": {"id": "default"}}, hv[1]],
        "fill": [{"properties": {"show": lit(True)}}, d[0], hv[0]],
        "outline": [{"properties": {"show": lit(con_borde)}}, d[2], hv[2]],
        "shape": [{"properties": {"tileShape": lit("rectangleRounded"), "roundEdge": lit(radio)}}],
    }
    vco = dict(SIN_TARJETA)
    if accion:
        tipo, destino = accion
        link = {"show": lit(True), "type": lit(tipo)}
        if tipo == "PageNavigation":
            link["navigationSection"] = lit(destino)
        elif tipo == "Bookmark":
            link["bookmark"] = lit(destino)
        vco["visualLink"] = [{"properties": link}]
    v = {"$schema": VC_SCHEMA, "name": nombre,
         "position": {"x": x, "y": y, "z": z, "width": wd, "height": h, "tabOrder": z},
         "visual": {"visualType": "actionButton", "objects": objects, "visualContainerObjects": vco,
                    "drillFilterOtherVisuals": True}}
    if padre:
        v["parentGroupName"] = padre
    if oculto:
        v["isHidden"] = True
    return v


def forma(nombre, x, y, wd, h, z, relleno, transp=0, radio=0, borde=None, padre=None):
    v = {"$schema": VC_SCHEMA, "name": nombre,
         "position": {"x": x, "y": y, "z": z, "width": wd, "height": h, "tabOrder": z},
         "visual": {"visualType": "shape", "objects": {
             "shape": [{"properties": {"tileShape": lit("rectangleRounded" if radio else "rectangle"),
                                       **({"roundEdge": lit(radio)} if radio else {})}}],
             "fill": [{"properties": {"show": lit(True)}},
                      {"properties": {"fillColor": color(relleno), "transparency": lit(transp)}, "selector": {"id": "default"}}],
             "outline": [{"properties": {"show": lit(borde is not None)}},
                         {"properties": {"lineColor": color(borde or relleno), "weight": lit(1),
                                         **({"roundEdge": lit(radio)} if radio else {})}, "selector": {"id": "default"}}],
             "line": [{"properties": {"lineColor": color(borde or relleno), "weight": lit(1 if borde else 0),
                                      "transparency": lit(0 if borde else 100), "roundEdge": lit(radio)}}]},
             "visualContainerObjects": dict(SIN_TARJETA)}}
    if padre:
        v["parentGroupName"] = padre
    return v


def texto_visual(nombre, x, y, wd, h, z, parrafos, padre=None):
    """parrafos: lista de listas de (texto, estilo)."""
    v = {"$schema": VC_SCHEMA, "name": nombre,
         "position": {"x": x, "y": y, "z": z, "width": wd, "height": h, "tabOrder": z},
         "visual": {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [
             {"textRuns": [{"value": t, "textStyle": {"fontFamily": "Segoe UI", **st}} for t, st in runs]}
             for runs in parrafos]}}]},
             "visualContainerObjects": dict(SIN_TARJETA)}}
    if padre:
        v["parentGroupName"] = padre
    return v


class Pagina:
    def __init__(self, nombre, display, app=True, ancho=1280, alto=720):
        self.nombre, self.display, self.visuales, self.z = nombre, display, [], 0
        self.app, self.ancho, self.alto = app, ancho, alto
        self.page_objects, self.interacciones, self.extra_page = None, [], {}
        self.marcadores = []  # (id, nombre visible, grupo, hijos, oculto)
        self.legacy = app  # posiciones heredadas del diseño anterior: se reescalan al nuevo cuerpo

    def _y(self, y, h):
        if self.legacy and y >= Y0_VIEJO:
            return round(Y0 + (y - Y0_VIEJO) * K), round(h * K)
        return y, h

    def add(self, vtype, x, y, wd, h, roles=None, title=None, objects=None, sort=None, extra_vco=None, nombre=None,
            pad=16, field_params=None, padre=None, oculto=False):
        self.z += 1
        y, h = self._y(y, h)
        v = {"visualType": vtype, "drillFilterOtherVisuals": True}
        if roles:
            v["query"] = {"queryState": {r: {"projections": p} for r, p in roles.items()}}
            for r, fp in (field_params or {}).items():
                v["query"]["queryState"][r]["fieldParameters"] = fp
            if sort:
                v["query"]["sortDefinition"] = {"sort": [{"field": sort[0]["field"], "direction": sort[1]}],
                                                "isDefaultSort": False}
        objects = dict(objects or {})
        if vtype in GRAFICOS:
            objects.setdefault("categoryAxis", [{"properties": {"showAxisTitle": lit(False), "labelColor": color(TXT2),
                                                                "gridlineShow": lit(False)}}])
            objects.setdefault("valueAxis", [{"properties": {"showAxisTitle": lit(False), "labelColor": color(TXT2),
                                                             "gridlineColor": color(LINEA)}}])
            objects.setdefault("legend", [{"properties": {"labelColor": color(TXT2)}}])
        if vtype in BARRAS and "labels" not in objects:
            objects["labels"] = [{"properties": {"show": lit(True), "fontSize": lit(8), "color": color(TXT)}}]
        if vtype == "tableEx":
            objects.setdefault("values", [{"properties": {"fontSize": lit(10)}}])
            objects.setdefault("columnHeaders", [{"properties": {"fontSize": lit(10)}}])
            objects.setdefault("total", [{"properties": {"fontSize": lit(10)}}])
        if vtype == "azureMap":
            objects.setdefault("mapControls", [{"properties": {
                "autoZoom": lit(False), "zoom": lit(MAPA_ZOOM.get(self.nombre, 3.2)),
                "centerLatitude": lit(38.5), "centerLongitude": lit(-96.5), "showStylePicker": lit(False),
                "defaultStyle": lit("grayscale_dark")}}])
            objects.setdefault("bubbleLayer", [{"properties": {"maxRadius": lit(16)}}])
        if objects:
            v["objects"] = objects
        vco = contenedor(titulo(title) if title else {"title": [{"properties": {"show": lit(False)}}]}, pad=pad)
        if extra_vco:
            vco.update(extra_vco)
        v["visualContainerObjects"] = vco
        cont = {"$schema": VC_SCHEMA, "name": nombre or f"{self.nombre}_{self.z:02d}_{vtype}",
                "position": {"x": x, "y": y, "z": self.z * 1000, "width": wd, "height": h, "tabOrder": self.z * 1000},
                "visual": v}
        if padre:
            cont["parentGroupName"] = padre
        if oculto:
            cont["isHidden"] = True
        self.visuales.append(cont)
        return cont

    def crudo(self, v):
        self.visuales.append(v)
        return v

    # ---------------------------------------------------------------- App Shell
    def app_shell(self, slicers, pie_medida="Texto Período"):
        """Barra de navegación de 48 px + cajón de filtros deslizable (oculto) + pie."""
        n_ = self.nombre
        self.z += 1  # z=1: banda (conserva el nombre _00_banda)
        self.crudo(forma(f"{n_}_00_banda", 0, 0, 1280, 48, 0, NAV))
        self.crudo(forma(f"{n_}_nav_linea", 0, 47, 1280, 1, 1, LINEA))
        self.z += 1  # z=2: logo ATLAS → portada
        self.crudo(boton(f"{n_}_02_logo", 12, 8, 104, 32, 2000, "◆ ATLAS", ("PageNavigation", "p0portada"),
                         texto_color=TXT, hover_texto=CIAN, tam=13, radio=8))
        for i, (pid, _, etiqueta, *_r) in enumerate(PAGINAS_APP):
            activa = pid == n_
            self.crudo(boton(f"{n_}_nav_{i}", 128 + i * 112, 10, 106, 28, 2100 + i, etiqueta,
                             None if activa else ("PageNavigation", pid),
                             fill=VIOLETA if activa else None, fill_t=0 if activa else 100,
                             texto_color="#FFFFFF" if activa else TXT2,
                             hover_fill=VIOLETA if activa else HOVER, hover_texto="#FFFFFF" if activa else TXT))
        grupo = f"{n_}_filtros"
        abrir, cerrar = hid(n_, "abrir"), hid(n_, "cerrar")
        self.z += 1  # z=3: botón Filtros (N)
        self.crudo(boton(f"{n_}_03_filtros", 1044, 10, 132, 28, 3000, "Filtros", ("Bookmark", abrir),
                         texto_color=CIAN, hover_texto=CIAN, borde=CIAN, hover_fill=HOVER,
                         texto_medida="Texto Boton Filtros"))
        self.z += 1  # z=4: Reset (borra todos los segmentadores)
        self.crudo(boton(f"{n_}_04_reset", 1184, 10, 84, 28, 4000, "↺  Reset", ("ClearAllSlicers", None),
                         borde=LINEA, hover_borde=TXT2))
        # cajón: fondo, borde izquierdo violeta, título, cerrar y segmentadores
        legacy, self.legacy = self.legacy, False
        hijos = []
        hijos.append(self.crudo(forma(f"{n_}_cajon_fondo", 980, 48, 300, 672, 60000, CARD, padre=grupo))["name"])
        hijos.append(self.crudo(forma(f"{n_}_cajon_borde", 980, 48, 3, 672, 60001, VIOLETA, padre=grupo))["name"])
        hijos.append(self.crudo(texto_visual(f"{n_}_cajon_titulo", 998, 60, 200, 32, 60002, [
            [("Filtros", {"fontSize": "14pt", "fontWeight": "bold", "color": TXT})]], padre=grupo))["name"])
        hijos.append(self.crudo(boton(f"{n_}_cajon_cerrar", 1236, 60, 30, 30, 60003, "✕", ("Bookmark", cerrar),
                                      texto_color=TXT2, hover_texto=TXT, tam=12, radio=15, padre=grupo))["name"])
        for i, (ent, prop, tit) in enumerate(slicers):
            sl = self.add("slicer", 998, 104 + i * 76, 266, 66, {"Values": [C(ent, prop)]}, objects={
                "data": [{"properties": {"mode": lit("Dropdown")}}],
                "header": [{"properties": {"show": lit(True), "text": lit(tit), "textSize": lit(9),
                                           "fontColor": color(TXT2)}}],
                "items": [{"properties": {"textSize": lit(10), "fontColor": color(TXT), "background": color(BG)}}]},
                extra_vco={"padding": [{"properties": {"top": lit(4), "bottom": lit(4), "left": lit(8), "right": lit(8)}}],
                           "background": [{"properties": {"show": lit(True), "color": color(BG)}}]},
                padre=grupo)
            sl["position"]["z"] = 60010 + i
            hijos.append(sl["name"])
        self.crudo({"$schema": VC_SCHEMA, "name": grupo,
                    "position": {"x": 980, "y": 48, "z": 59999, "width": 300, "height": 672, "tabOrder": 59999},
                    "visualGroup": {"displayName": "Cajón de filtros", "groupMode": "ScaleMode"}, "isHidden": True})
        self.legacy = legacy
        for v in self.visuales:  # dentro de un grupo, x/y son relativos al grupo
            if v.get("parentGroupName") == grupo:
                v["position"]["x"] -= 980
                v["position"]["y"] -= 48
        self.marcadores += [(abrir, f"Abrir_Filtros · {self.display}", grupo, hijos, False),
                            (cerrar, f"Cerrar_Filtros · {self.display}", grupo, hijos, True)]
        self.pie_medida = pie_medida

    def pie(self):
        self.legacy = False
        self.add("card", 20, 696, 700, 22, {"Values": [M("Texto Fuente")]}, objects={
            "labels": [{"properties": {"color": color(TXT2), "fontSize": lit(8)}}],
            "categoryLabels": [{"properties": {"show": lit(False)}}]}, extra_vco=SIN_TARJETA)
        if self.app:
            c = self.add("card", 760, 696, 500, 22, {"Values": [M(self.pie_medida)]}, objects={
                "labels": [{"properties": {"color": color(TXT2), "fontSize": lit(8)}}],
                "categoryLabels": [{"properties": {"show": lit(False)}}]}, extra_vco=SIN_TARJETA,
                nombre=f"{self.nombre}_pie_periodo")
            self.z -= 1  # no consume numeración de visuales heredados


def kpis(p, y, medidas):
    n_ = len(medidas)
    wd = (1240 - (n_ - 1) * 12) // n_
    for i, (m, tit) in enumerate(medidas):
        p.add("card", 20 + i * (wd + 12), y, wd, 92, {"Values": [M(m)]}, title=tit, objects={
            "labels": [{"properties": {"color": color(TXT), "fontSize": lit(22), "labelDisplayUnits": lit(1)}}],
            "categoryLabels": [{"properties": {"show": lit(False)}}]}, pad=10)


def kpis_nuevas(p, y, medidas, imagenes):
    """Tarjetas nuevas (cardVisual) con acento superior cian y SVG opcional."""
    n_ = len(medidas)
    wd = (1240 - (n_ - 1) * 12) // n_
    for i, (m, tit) in enumerate(medidas):
        ref = f"Medidas.{m}"
        proj = M(m)
        proj["displayName"] = proj["nativeQueryRef"] = tit
        objects = {
            "value": [{"properties": {"fontSize": lit(20), "fontColor": color(TXT), "bold": lit(True),
                                      "labelDisplayUnits": lit(1), "displayUnits": lit(1)},
                       "selector": {"metadata": ref}}],
            "label": [{"properties": {"show": lit(True), "fontColor": color(TXT2), "fontSize": lit(10),
                                      "position": lit("aboveValue")}, "selector": {"metadata": ref}}],
        }
        objects["outline"] = [{"properties": {"show": lit(False)}}]
        objects["fillCustom"] = [{"properties": {"show": lit(False)}}]
        if m in imagenes:
            objects["value"][0]["properties"]["fontSize"] = lit(17)
            objects["label"][0]["properties"]["fontSize"] = lit(9)
            objects["cardImage"] = [{"properties": {"show": lit(True)}, "selector": {"metadata": ref}},
                                    {"properties": {"imageType": lit("imageUrl"), "imageUrl": expr_medida(imagenes[m]),
                                                    "imageHeight": lit(18)}, "selector": {"metadata": ref}}]
        c = p.add("cardVisual", 20 + i * (wd + 12), y, wd, 98, {"Data": [proj]}, objects=objects, pad=4)
        yy = c["position"]["y"]
        p.crudo(forma(f"{p.nombre}_kpi_acento_{i}", 20 + i * (wd + 12) + 12, yy, wd - 24, 2, c["position"]["z"] + 1, CIAN))


def barras_color(medida_color="Color Puntualidad"):
    return {"dataPoint": [{"properties": {"fill": color_medida(medida_color)},
                           "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]}


def imagen_tabla(alto, ancho=None):
    return {"grid": [{"properties": {"imageHeight": lit(alto), **({"imageWidth": lit(ancho)} if ancho else {}),
                                     "gridHorizontalColor": color(LINEA), "gridVerticalColor": color(LINEA)}}]}


SLICERS_STD = [("dMes", "Anio", "Año"), ("dMes", "Mes", "Mes"), ("dAerolinea", "Aerolinea", "Aerolínea"),
               ("dOrigen", "OrigenEstado", "Estado de origen"), ("dOrigen", "OrigenCodigo", "Aeropuerto de origen")]
SLICERS_PATRON = [("dMes", "Anio", "Año"), ("dMes", "Mes", "Mes"), ("dAerolinea", "Aerolinea", "Aerolínea"),
                  ("dAerolinea", "TipoAerolinea", "Tipo de aerolínea")]
SLICERS_DETALLE = [("dAerolinea", "Aerolinea", "Aerolínea"), ("dOrigen", "OrigenCodigo", "Aeropuerto de origen"),
                   ("dDestino", "DestinoCodigo", "Aeropuerto de destino"),
                   ("dCausaCancelacion", "CausaCancelacion", "Causa de cancelación"), ("dHora", "FranjaHoraria", "Franja")]
SLICERS_BENCH = [("dMes", "Anio", "Año"), ("dMes", "Mes", "Mes"), ("dAerolinea", "TipoAerolinea", "Tipo de aerolínea"),
                 ("dOrigen", "OrigenEstado", "Estado de origen"), ("dOrigen", "OrigenCodigo", "Aeropuerto de origen")]

TOOLTIP_AEROPUERTO = {"visualTooltip": [{"properties": {"show": lit(True), "type": lit("Canvas"),
                                                        "section": lit("p8tooltip")}}]}


def portada():
    p = Pagina("p0portada", "Portada", app=False)
    p.page_objects = {"background": [{"properties": {
        "image": {"image": {"name": lit("Portada"), "url": {"expr": {"ResourcePackageItem": {
            "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": FONDO_PORTADA}}},
            "scaling": lit("Fit")}},
        "transparency": lit(0)}}],
        "outspace": [{"properties": {"color": color(BG)}}]}
    v = p.crudo
    v(texto_visual("p0portada_marca", 48, 32, 140, 40, 1000, [[("ATLAS", {"fontSize": "22pt", "fontWeight": "bold",
                                                                           "color": TXT})]]))
    v(boton("p0portada_badge", 168, 40, 250, 24, 1001, "AVIATION INTELLIGENCE  •  BTS DATA", None,
            texto_color=CIAN, hover_texto=CIAN, hover_fill=None, hover_t=100, borde=CIAN, tam=8, radio=12))
    v(texto_visual("p0portada_titulo", 44, 150, 600, 120, 1002, [
        [("BSI Transporte", {"fontSize": "34pt", "fontWeight": "bold", "color": TXT})],
        [("Aéreo EEUU", {"fontSize": "34pt", "fontWeight": "bold", "color": CIAN})]]))
    v(texto_visual("p0portada_subtitulo", 44, 282, 560, 60, 1003, [
        [("Análisis Ejecutivo de Puntualidad, Demoras y Eficiencia Operativa (Sep 2023 – Ago 2026)",
          {"fontSize": "13pt", "color": TXT2})]]))
    for i, (m, et) in enumerate([("Portada Vuelos", "Vuelos analizados"), ("Portada Puntualidad", "Puntualidad global"),
                                 ("Portada Demora", "Demora media")]):
        x = 48 + i * 188
        v(forma(f"p0portada_kpi_vidrio_{i}", x, 372, 176, 104, 1010 + i, "#FFFFFF", transp=94, radio=14, borde="#2A3350"))
        v(forma(f"p0portada_kpi_acento_{i}", x + 16, 372, 40, 2, 1013 + i, [CIAN, VERDE, AMBAR][i]))
        c = p.add("card", x + 4, 384, 168, 50, {"Values": [M(m)]}, objects={
            "labels": [{"properties": {"color": color(TXT), "fontSize": lit(24)}}],
            "categoryLabels": [{"properties": {"show": lit(False)}}]}, extra_vco=SIN_TARJETA,
            nombre=f"p0portada_kpi_{i}")
        c["position"]["z"] = 1020 + i
        v(texto_visual(f"p0portada_kpi_et_{i}", x + 12, 436, 160, 28, 1023 + i,
                       [[(et.upper(), {"fontSize": "8pt", "fontWeight": "bold", "color": TXT2})]]))
    v(texto_visual("p0portada_fuente", 44, 660, 600, 28, 1030, [
        [("Fuente: BTS – Reporting Carrier On-Time Performance (transtats.bts.gov) · 21,1 M de vuelos · Elaboración ATLAS",
          {"fontSize": "8pt", "color": "#64748B"})]]))
    # grilla de lanzadores: 2 columnas × 3 filas + el 7º a lo ancho
    for i, (pid, _, _, tit, desc) in enumerate(PAGINAS_APP):
        if i < 6:
            x, y, wd = 668 + (i % 2) * 292, 128 + (i // 2) * 120, 280
        else:
            x, y, wd = 668, 488, 572
        v(forma(f"p0portada_tile_fondo_{i}", x, y, wd, 108, 2000 + i, CARD, transp=12, radio=12, borde=LINEA))
        v(texto_visual(f"p0portada_tile_texto_{i}", x + 14, y + 12, wd - 50, 88, 2010 + i, [
            [(f"{i + 1:02d}", {"fontSize": "9pt", "fontWeight": "bold", "color": CIAN})],
            [(tit, {"fontSize": "13pt", "fontWeight": "bold", "color": TXT})],
            [(desc, {"fontSize": "9pt", "color": TXT2})]]))
        v(texto_visual(f"p0portada_tile_flecha_{i}", x + wd - 36, y + 38, 28, 32, 2020 + i,
                       [[("→", {"fontSize": "16pt", "color": VIOLETA})]]))
        v(boton(f"p0portada_tile_{i}", x, y, wd, 108, 2030 + i, "", ("PageNavigation", pid),
                fill=None, fill_t=100, hover_fill=CIAN, hover_t=92, borde=None, hover_borde=CIAN, radio=12))
    return p


def benchmark():
    p = Pagina("p7benchmark", "Benchmark")
    p.legacy = False
    p.app_shell(SLICERS_BENCH)
    # selector visual de aerolíneas (Button Slicer con insignias)
    sl = p.add("advancedSlicerVisual", 16, 58, 1248, 78, {"Values": [C("dAerolinea", "Logo_SVG_URL")]}, objects={
        "layout": [{"properties": {"rowCount": {"expr": {"Literal": {"Value": "1L"}}},
                                   "columnCount": {"expr": {"Literal": {"Value": "15L"}}}}}],
        "selection": [{"properties": {"strictSingleSelect": lit(True)}}],
        "image": [{"properties": {"show": lit(True), "setAsBackGround": lit(True)}, "selector": {"id": "default"}},
                  {"properties": {"image": expr_medida("Selector_Aerolinea_SVG")},
                   "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "id": "default",
                                "hierarchyMatching": 1}}],
        "value": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}, {"properties": {"show": lit(False)}}],
        "label": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
        "fillCustom": [{"properties": {"show": lit(True), "fillColor": color(CARD), "transparency": lit(0)},
                        "selector": {"id": "default"}},
                       {"properties": {"fillColor": color(HOVER)}, "selector": {"id": "interaction:hover"}},
                       {"properties": {"fillColor": color(HOVER)}, "selector": {"id": "selection:selected"}}],
        "outline": [{"properties": {"show": lit(True), "lineColor": color(LINEA)}, "selector": {"id": "default"}},
                    {"properties": {"lineColor": color(CIAN), "weight": lit(2)}, "selector": {"id": "selection:selected"}}],
        "shapeCustomRectangle": [{"properties": {"tileShape": lit("rectangleRoundedByPixel"),
                                                 "rectangleRoundedCurve": {"expr": {"Literal": {"Value": "10L"}}}},
                                  "selector": {"id": "default"}}],
    }, pad=6, nombre="p7benchmark_selector")
    hero = p.add("tableEx", 16, 146, 412, 290, {"Values": [M("Benchmark_Hero_SVG")]}, objects={
        **imagen_tabla(246, 368),
        "columnHeaders": [{"properties": {"backColor": color(CARD), "fontColor": color(CARD), "fontSize": lit(1)}}],
        "total": [{"properties": {"totals": lit(False)}}],
        "values": [{"properties": {"backColorPrimary": color(CARD), "backColorSecondary": color(CARD)}}]},
        pad=4, nombre="p7benchmark_perfil")
    sc = p.add("scatterChart", 440, 146, 824, 290, {
        "Category": [C("dAerolinea", "AerolineaCod")], "Series": [C("dAerolinea", "TipoAerolinea")],
        "X": [M("Vuelos")], "Y": [M("% A Tiempo")]}, title="Cuadrante estratégico: escala vs. puntualidad", objects={
        "categoryLabels": [{"properties": {"show": lit(True), "color": color(TXT), "fontSize": lit(9)}}],
        "xAxisReferenceLine": [{"properties": {"show": lit(True), "value": expr_medida("Vuelos Promedio por Aerolínea"),
                                               "lineColor": color(GRIS_IND), "style": lit("dashed"),
                                               "transparency": lit(20)}, "selector": {"id": "0"}}],
        "y1AxisReferenceLine": [{"properties": {"show": lit(True), "value": expr_medida("% A Tiempo Industria"),
                                                "lineColor": color(GRIS_IND), "style": lit("dashed"),
                                                "transparency": lit(20)}, "selector": {"id": "0"}}],
    }, nombre="p7benchmark_cuadrante")
    ln = p.add("lineChart", 16, 446, 520, 242, {"Category": [C("dMes", "FechaMes")],
                                                 "Y": [M("% A Tiempo"), M("% A Tiempo Industria")]},
               title="Evolución vs. promedio de la industria", sort=(C("dMes", "FechaMes"), "Ascending"), objects={
        "dataPoint": [{"properties": {"fill": color(CIAN)}, "selector": {"metadata": "Medidas.% A Tiempo"}},
                      {"properties": {"fill": color(GRIS_IND)}, "selector": {"metadata": "Medidas.% A Tiempo Industria"}}],
        "lineStyles": [{"properties": {"strokeWidth": lit(3)}, "selector": {"metadata": "Medidas.% A Tiempo"}},
                       {"properties": {"lineStyle": lit("dashed"), "strokeWidth": lit(2)},
                        "selector": {"metadata": "Medidas.% A Tiempo Industria"}}]}, nombre="p7benchmark_evolucion")
    rk = p.add("tableEx", 548, 446, 716, 242, {"Values": [
        M("Ranking Industria"), C("dAerolinea", "Logo_SVG_URL"), C("dAerolinea", "Aerolinea"),
        C("dAerolinea", "TipoAerolinea"), M("Vuelos"), M("Tabla_Barra_Puntualidad_SVG"), M("Tabla_Badge_Variacion_SVG"),
        M("Demora Promedio de Demorados"), M("% Cancelados")]}, title="Ranking de aerolíneas",
        sort=(M("Ranking Industria"), "Ascending"), objects=imagen_tabla(24, 130), nombre="p7benchmark_ranking")
    rk["visual"]["query"]["queryState"]["Values"]["projections"][1]["displayName"] = "Logo"
    rk["visual"]["query"]["queryState"]["Values"]["projections"][2]["displayName"] = "Aerolínea"
    p.interacciones = [{"source": sl["name"], "target": t["name"], "type": "NoFilter"} for t in (sc, rk)]
    p.pie()
    return p


def tooltip_aeropuerto():
    p = Pagina("p8tooltip", "Tooltip_Aeropuerto", app=False, ancho=320, alto=200)
    p.extra_page = {"type": "Tooltip", "visibility": "HiddenInViewMode",
                    "pageBinding": {"name": "TooltipAeropuerto", "type": "Tooltip", "parameters": []}}
    p.page_objects = {"background": [{"properties": {"color": color(CARD), "transparency": lit(0)}}]}
    p.crudo(forma("p8tooltip_acento", 0, 0, 320, 3, 500, CIAN))
    p.add("card", 8, 8, 220, 30, {"Values": [M("Tooltip Aeropuerto Titulo")]}, objects={
        "labels": [{"properties": {"color": color(TXT), "fontSize": lit(11)}}],
        "categoryLabels": [{"properties": {"show": lit(False)}}]}, extra_vco=SIN_TARJETA, nombre="p8tooltip_titulo")
    p.add("card", 232, 6, 80, 34, {"Values": [M("% A Tiempo")]}, objects={
        "labels": [{"properties": {"color": color_medida("Color Puntualidad"), "fontSize": lit(16)}}],
        "categoryLabels": [{"properties": {"show": lit(False)}}]}, extra_vco=SIN_TARJETA, nombre="p8tooltip_puntualidad")
    p.crudo(texto_visual("p8tooltip_sub", 8, 44, 300, 22, 501, [[("TOP 3 RUTAS MÁS DEMORADAS",
                                                                  {"fontSize": "8pt", "fontWeight": "bold", "color": TXT2})]]))
    p.add("tableEx", 4, 66, 312, 128, {"Values": [M("Tooltip_Top3_Rutas_SVG")]}, objects={
        **imagen_tabla(90, 300),
        "columnHeaders": [{"properties": {"backColor": color(CARD), "fontColor": color(CARD), "fontSize": lit(1)}}],
        "total": [{"properties": {"totals": lit(False)}}],
        "values": [{"properties": {"backColorPrimary": color(CARD), "backColorSecondary": color(CARD)}}]},
        extra_vco=SIN_TARJETA, nombre="p8tooltip_rutas")
    return p


def paginas():
    P = [portada()]
    # 1 RESUMEN ---------------------------------------------------------------
    p = Pagina("p1resumen", "Resumen")
    p.app_shell(SLICERS_STD, pie_medida="Titulo Dinamico")
    kpis_nuevas(p, 136, [("Vuelos", "Vuelos"), ("% A Tiempo", "% a tiempo"), ("Δ % A Tiempo 12M", "Δ últimos 12 meses (pp)"),
                         ("% Cancelados", "% cancelados"), ("Demora Promedio de Demorados", "Demora media de demorados"),
                         ("Horas de Demora", "Horas de demora")],
                {"% A Tiempo": "KPI_Sparkline_Puntualidad_SVG", "Δ % A Tiempo 12M": "KPI_Bullet_Meta_SVG"})
    p.add("lineChart", 20, 240, 760, 220, {"Category": [C("dMes", "FechaMes")],
                                           "Y": [M("% A Tiempo"), M("% A Tiempo Móvil 3M")]},
          title="Evolución mensual del % a tiempo", sort=(C("dMes", "FechaMes"), "Ascending"))
    p.add("clusteredBarChart", 792, 240, 468, 450, {"Category": [C("dAerolinea", "Aerolinea")], "Y": [M("% A Tiempo")]},
          title="% a tiempo por aerolínea", objects=barras_color(), sort=(M("% A Tiempo"), "Descending"))
    p.add("azureMap", 20, 470, 760, 220, {"Category": [C("dOrigen", "OrigenCodigo")], "Y": [PROM("dOrigen", "OrigenLatitud")],
                                     "X": [PROM("dOrigen", "OrigenLongitud")], "Size": [M("Vuelos")],
                                     "Tooltips": [M("% A Tiempo"), M("Demora Promedio Llegada")]},
          title="Aeropuertos de origen (tamaño = vuelos)")
    p.pie()
    P.append(p)

    # 2 COMPARATIVO -----------------------------------------------------------
    p = Pagina("p2aerolineas", "Comparativo")
    p.app_shell(SLICERS_STD)
    p.add("tableEx", 20, 136, 1240, 286, {"Values": [
        C("dAerolinea", "Aerolinea"), C("dAerolinea", "TipoAerolinea"), M("Ranking Aerolínea"), M("Vuelos"),
        M("Tabla_Barra_Puntualidad_SVG"), M("Tabla_Badge_Variacion_SVG"), M("% Cancelados"),
        M("Demora Promedio de Demorados"), M("% Causa Controlable"), M("Taxi Salida Promedio")]},
        title="Tabla de desempeño (ordenar por columna)",
        sort=(M("Ranking Aerolínea"), "Ascending"), objects={**imagen_tabla(22, 130), "columnFormatting": [
            {"properties": {"dataBars": {"positiveColor": color("#4B3A8C"), "negativeColor": color(ROJO),
                                         "axisColor": color(LINEA), "reverseDirection": lit(False), "hideText": lit(False)}},
             "selector": {"metadata": "Medidas.Vuelos"}}]})
    p.add("lineChart", 20, 432, 470, 258, {"Category": [C("dMes", "FechaMes")],
                                           "Series": [C("dAerolinea", "TipoAerolinea")], "Y": [M("% A Tiempo")]},
          title="% a tiempo: troncales vs regionales vs low cost", sort=(C("dMes", "FechaMes"), "Ascending"))
    p.add("clusteredBarChart", 502, 432, 374, 258, {"Category": [C("dAerolinea", "Aerolinea")], "Y": [M("Vuelos")]},
          title="Vuelos por aerolínea", sort=(M("Vuelos"), "Descending"))
    p.add("clusteredBarChart", 888, 432, 372, 258, {"Category": [C("dAerolinea", "Aerolinea")], "Y": [M("% Cancelados")]},
          title="% cancelados por aerolínea", sort=(M("% Cancelados"), "Descending"))
    p.pie()
    P.append(p)

    P.append(benchmark())

    # 3 AEROPUERTOS Y RUTAS ---------------------------------------------------
    p = Pagina("p3aeropuertos", "Aeropuertos y rutas")
    p.app_shell(SLICERS_STD)
    p.add("azureMap", 20, 136, 620, 554, {"Category": [C("dOrigen", "OrigenCodigo")], "Y": [PROM("dOrigen", "OrigenLatitud")],
                                     "X": [PROM("dOrigen", "OrigenLongitud")], "Size": [M("Vuelos Demorados")],
                                     "Tooltips": [M("Vuelos"), M("% A Tiempo"), M("Demora Promedio de Demorados")]},
          title="Vuelos demorados por aeropuerto de origen", extra_vco=TOOLTIP_AEROPUERTO)
    p.add("tableEx", 652, 136, 608, 272, {"Values": [
        C("dOrigen", "OrigenCodigo"), C("dOrigen", "OrigenCiudad"), C("dOrigen", "OrigenEstadoCod"), M("Vuelos"),
        M("Tabla_Barra_Puntualidad_SVG"), M("% Cancelados"), M("Taxi Salida Promedio")]},
          title="Aeropuertos de origen (ordenar por columna)", sort=(M("Vuelos"), "Descending"),
          objects=imagen_tabla(20, 130), extra_vco=TOOLTIP_AEROPUERTO)
    p.add("tableEx", 652, 418, 608, 272, {"Values": [
        C("dOrigen", "OrigenCodigo"), C("dDestino", "DestinoCodigo"), M("Vuelos"), M("Tabla_Barra_Puntualidad_SVG"),
        M("% Cancelados"), M("Demora Promedio de Demorados")]},
          title="Rutas (origen → destino)", sort=(M("Vuelos"), "Descending"), objects=imagen_tabla(20, 130))
    p.pie()
    P.append(p)

    # 4 CAUSAS ----------------------------------------------------------------
    p = Pagina("p4causas", "Causas de demora")
    p.app_shell(SLICERS_STD)
    kpis(p, 136, [(f"% Causa {c}", ETIQ_CAUSA[c]) for c, _ in CAUSAS] + [("% Causa Controlable", "Controlable por aerolínea")])
    p.add("columnChart", 20, 240, 760, 220, {"Category": [C("dMes", "FechaMes")],
                                             "Y": [M(f"Min Demora {c}") for c, _ in CAUSAS]},
          title="Minutos de demora por causa y mes", sort=(C("dMes", "FechaMes"), "Ascending"))
    p.add("clusteredBarChart", 792, 240, 468, 220, {"Category": [C("dCausaCancelacion", "CausaCancelacion")],
                                                    "Y": [M("Cancelados por Causa")]},
          title="Cancelaciones por causa", sort=(M("Cancelados por Causa"), "Descending"))
    p.add("barChart", 20, 470, 1240, 220, {"Category": [C("dAerolinea", "Aerolinea")],
                                           "Y": [M(f"% Causa {c}") for c, _ in CAUSAS]},
          title="Mezcla de causas por aerolínea (% de minutos de demora)", sort=(M("% Causa Aerolínea"), "Descending"))
    p.pie()
    P.append(p)

    # 5 PATRONES --------------------------------------------------------------
    p = Pagina("p5patrones", "Patrones horarios")
    p.app_shell(SLICERS_PATRON)
    fp_col = {"Column": {"Expression": {"SourceRef": {"Entity": FP}}, "Property": FP}}
    proj_fp = {"field": fp_col, "queryRef": f"{FP}.{FP}", "nativeQueryRef": "Métrica"}
    p.add("pivotTable", 20, 136, 1240, 226, {"Rows": [C("dDiaSemana", "DiaSemana")], "Columns": [C("dHora", "HoraTexto")],
                                             "Values": [proj_fp]},
          title="Matriz térmica: día × hora programada de salida",
          field_params={"Values": [{"parameterExpr": fp_col, "index": 0, "length": 1}]},
          objects={"values": [{"properties": {"backColor": color_medida(col_), "fontColor": color(TXT)},
                               "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                            "metadata": f"Medidas.{m}"}} for _, m, col_ in METRICAS_HEATMAP]})
    p.add("lineChart", 20, 372, 610, 318, {"Category": [C("dMes", "Mes")], "Series": [C("dMes", "Anio")],
                                           "Y": [M("% A Tiempo")]},
          title="Estacionalidad: % a tiempo por mes y año", sort=(C("dMes", "Mes"), "Ascending"))
    p.add("clusteredColumnChart", 642, 372, 300, 318, {"Category": [C("dHora", "FranjaHoraria")], "Y": [M("P % A Tiempo")]},
          title="% a tiempo por franja", objects=barras_color("Color P % A Tiempo"),
          sort=(C("dHora", "FranjaHoraria"), "Ascending"))
    p.add("clusteredColumnChart", 954, 372, 306, 318, {"Category": [C("dDiaSemana", "DiaSemana")], "Y": [M("P % Cancelados")]},
          title="% cancelados por día", sort=(C("dDiaSemana", "DiaSemana"), "Ascending"))
    # selector de métrica (botones) en la cabecera de la matriz
    filtro_fp = {"filter": {"Version": 2, "From": [{"Name": "s", "Entity": FP, "Type": 0}],
                            "Where": [{"Condition": {"In": {
                                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": FP}}],
                                "Values": [[{"Literal": {"Value": f"'{METRICAS_HEATMAP[0][0]}'"}}]]}}}]}}
    sel = p.add("advancedSlicerVisual", 760, 62, 490, 38, {"Values": [proj_fp]}, objects={
        "layout": [{"properties": {"rowCount": {"expr": {"Literal": {"Value": "1L"}}},
                                   "columnCount": {"expr": {"Literal": {"Value": "3L"}}}}}],
        "selection": [{"properties": {"strictSingleSelect": lit(True)}}],
        "general": [{"properties": {"filter": filtro_fp}}],
        "value": [{"properties": {"fontColor": color(TXT2), "fontSize": lit(9)}, "selector": {"id": "default"}},
                  {"properties": {"fontColor": color("#FFFFFF"), "bold": lit(True)}, "selector": {"id": "selection:selected"}}],
        "fillCustom": [{"properties": {"show": lit(True), "fillColor": color(BG), "transparency": lit(0)},
                        "selector": {"id": "default"}},
                       {"properties": {"fillColor": color(VIOLETA)}, "selector": {"id": "selection:selected"}}],
        "outline": [{"properties": {"show": lit(True), "lineColor": color(LINEA)}, "selector": {"id": "default"}}],
        "shapeCustomRectangle": [{"properties": {"tileShape": lit("rectangleRoundedByPixel"),
                                                 "rectangleRoundedCurve": {"expr": {"Literal": {"Value": "14L"}}}},
                                  "selector": {"id": "default"}}],
    }, extra_vco=SIN_TARJETA, nombre="p5patrones_selector_metrica")
    sel["position"]["z"] = 50000
    p.pie()
    P.append(p)

    # 6 DETALLE ---------------------------------------------------------------
    p = Pagina("p6detalle", "Detalle de vuelos")
    p.app_shell(SLICERS_DETALLE, pie_medida="Texto Detalle")
    p.add("tableEx", 20, 136, 1240, 554, {"Values": [
        C("fDetalle", "Fecha"), C("dAerolinea", "Aerolinea"), C("fDetalle", "NroVuelo"), C("fDetalle", "Ruta"),
        C("dHora", "HoraTexto"), C("fDetalle", "DemoraSalidaMin"), C("fDetalle", "DemoraLlegadaMin"),
        M("Vuelo_Estado_Badge_SVG"), C("fDetalle", "DistanciaMillas")]}, title="Vuelos",
        sort=(C("fDetalle", "DemoraLlegadaMin"), "Descending"),
        objects={**imagen_tabla(22, 150), "total": [{"properties": {"totals": lit(False)}}],
                 "values": [{"properties": {"fontSize": lit(10)}},
                            {"properties": {"backColor": color_medida("Color Demora Llegada")},
                             "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                          "metadata": "fDetalle.DemoraLlegadaMin"}}]})
    p.pie()
    P.append(p)
    P.append(tooltip_aeropuerto())
    return P


TEMA = {
    "name": "ATLAS Dark Executive UI",
    "dataColors": PALETA,
    "foreground": TXT, "foregroundNeutralSecondary": TXT2, "foregroundNeutralTertiary": GRIS_IND,
    "background": CARD, "backgroundLight": HOVER, "backgroundNeutral": LINEA,
    "tableAccent": VIOLETA, "good": VERDE, "neutral": AMBAR, "bad": ROJO,
    "maximum": ROJO, "center": AMBAR, "minimum": VERDE, "hyperlink": CIAN,
    "textClasses": {
        "title": {"fontFace": "Segoe UI Semibold", "color": TXT, "fontSize": 11},
        "callout": {"fontFace": "Segoe UI Semibold", "color": TXT, "fontSize": 24},
        "label": {"fontFace": "Segoe UI", "color": TXT2, "fontSize": 9},
        "header": {"fontFace": "Segoe UI Semibold", "color": TXT, "fontSize": 12},
        "largeTitle": {"fontFace": "Segoe UI Semibold", "color": TXT, "fontSize": 14},
    },
    "visualStyles": {
        "page": {"*": {"background": [{"color": {"solid": {"color": BG}}, "transparency": 0}],
                       "outspace": [{"color": {"solid": {"color": BG}}}]}},
        "*": {"*": {
            "background": [{"show": True, "color": {"solid": {"color": CARD}}, "transparency": 0}],
            "border": [{"show": True, "color": {"solid": {"color": LINEA}}, "radius": 12}],
            "padding": [{"top": 16, "bottom": 16, "left": 16, "right": 16}],
            "dropShadow": [{"show": False}],
            "title": [{"fontColor": {"solid": {"color": TXT}}, "fontSize": 11}],
            "categoryAxis": [{"labelColor": {"solid": {"color": TXT2}}, "gridlineColor": {"solid": {"color": LINEA}}}],
            "valueAxis": [{"labelColor": {"solid": {"color": TXT2}}, "gridlineColor": {"solid": {"color": LINEA}}}],
            "legend": [{"labelColor": {"solid": {"color": TXT2}}}],
            "labels": [{"color": {"solid": {"color": TXT}}}],
            "visualTooltip": [{"background": {"solid": {"color": CARD}}, "titleFontColor": {"solid": {"color": TXT2}},
                               "valueFontColor": {"solid": {"color": TXT}}}],
        }},
        **{vt: {"*": {"background": [{"show": False}], "border": [{"show": False}], "dropShadow": [{"show": False}],
                      "padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0}]}}
           for vt in ("textbox", "shape", "basicShape", "image", "actionButton")},
        "tableEx": {"*": {
            "columnHeaders": [{"backColor": {"solid": {"color": HOVER}}, "fontColor": {"solid": {"color": TXT}}}],
            "values": [{"backColorPrimary": {"solid": {"color": CARD}}, "backColorSecondary": {"solid": {"color": FILA_ALT}},
                        "fontColorPrimary": {"solid": {"color": TXT}}, "fontColorSecondary": {"solid": {"color": TXT}}}],
            "total": [{"backColor": {"solid": {"color": HOVER}}, "fontColor": {"solid": {"color": TXT}}}],
            "grid": [{"gridHorizontalColor": {"solid": {"color": LINEA}}, "gridVerticalColor": {"solid": {"color": LINEA}},
                      "outlineColor": {"solid": {"color": LINEA}}}]}},
        "pivotTable": {"*": {
            "columnHeaders": [{"backColor": {"solid": {"color": HOVER}}, "fontColor": {"solid": {"color": TXT}}}],
            "rowHeaders": [{"backColor": {"solid": {"color": HOVER}}, "fontColor": {"solid": {"color": TXT}}}],
            "values": [{"backColorPrimary": {"solid": {"color": CARD}}, "backColorSecondary": {"solid": {"color": CARD}},
                        "fontColorPrimary": {"solid": {"color": TXT}}}],
            "grid": [{"gridHorizontalColor": {"solid": {"color": BG}}, "gridVerticalColor": {"solid": {"color": BG}}}]}},
        "slicer": {"*": {
            "items": [{"fontColor": {"solid": {"color": TXT}}, "background": {"solid": {"color": BG}}}],
            "header": [{"fontColor": {"solid": {"color": TXT2}}}]}},
    },
}


def fondo_portada(path: Path):
    """Fondo de la portada: grilla tipo radar, resplandores violeta/cian y arcos de rutas aéreas (PNG 2560×1440)."""
    from PIL import Image, ImageDraw, ImageFilter
    S = 2
    W, Hh = 1280 * S, 720 * S
    base = Image.new("RGB", (W, Hh), BG)

    def resplandor(cx, cy, r, rgb, alpha):
        capa = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
        ImageDraw.Draw(capa).ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*rgb, alpha))
        return capa.filter(ImageFilter.GaussianBlur(r * 0.55))

    base = base.convert("RGBA")
    base = Image.alpha_composite(base, resplandor(330 * S, 300 * S, 300 * S, (124, 77, 255), 70))
    base = Image.alpha_composite(base, resplandor(1050 * S, 560 * S, 280 * S, (0, 229, 255), 45))
    g = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    for x in range(0, W, 40 * S):  # grilla
        d.line([(x, 0), (x, Hh)], fill=(148, 163, 184, 14), width=1)
    for y in range(0, Hh, 40 * S):
        d.line([(0, y), (W, y)], fill=(148, 163, 184, 14), width=1)
    cx, cy = 330 * S, 330 * S  # radar
    for r in range(60, 560, 70):
        d.ellipse([cx - r * S, cy - r * S, cx + r * S, cy + r * S], outline=(124, 77, 255, 34), width=S)
    for ang in range(0, 360, 30):
        a = math.radians(ang)
        d.line([(cx, cy), (cx + math.cos(a) * 560 * S, cy + math.sin(a) * 560 * S)], fill=(124, 77, 255, 18), width=1)
    rutas = [((80, 600), (620, 120), 0.35), ((200, 690), (1200, 90), 0.25), ((600, 700), (1250, 300), 0.3),
             ((40, 380), (700, 640), -0.25), ((900, 40), (1270, 520), 0.2)]
    for (x0, y0), (x1, y1), curva in rutas:  # arcos de rutas (Bézier cuadrática)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        nx, ny = -(y1 - y0), (x1 - x0)
        px, py = mx + nx * curva, my + ny * curva
        pts = [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * px + t ** 2 * x1,
                (1 - t) ** 2 * y0 + 2 * (1 - t) * t * py + t ** 2 * y1) for t in [i / 120 for i in range(121)]]
        d.line([(x * S, y * S) for x, y in pts], fill=(0, 229, 255, 55), width=S, joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse([(x - 3) * S, (y - 3) * S, (x + 3) * S, (y + 3) * S], fill=(0, 229, 255, 150))
    base = Image.alpha_composite(base, g)
    # velo oscuro a la derecha para que la grilla de lanzadores se lea bien
    velo = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
    ImageDraw.Draw(velo).rectangle([640 * S, 0, W, Hh], fill=(11, 14, 20, 90))
    base = Image.alpha_composite(base, velo.filter(ImageFilter.GaussianBlur(60 * S)))
    path.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(path, optimize=True)


def escribir_reporte():
    r = OUT / RP
    d = r / "definition"
    w(r / "definition.pbir", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{SM}"}}}, indent=2))
    # recursos de tema e imágenes
    sr = r / "StaticResources" / "SharedResources" / "BaseThemes"
    sr.mkdir(parents=True, exist_ok=True)
    shutil.copy(PBI_THEMES / f"{BASE_THEME}.json", sr / f"{BASE_THEME}.json")
    rr = r / "StaticResources" / "RegisteredResources"
    rr.mkdir(parents=True, exist_ok=True)
    tema = json.dumps(TEMA, indent=2, ensure_ascii=False)
    w(rr / TEMA_ARCHIVO, tema)
    w(BASE / "Theme" / TEMA_ARCHIVO, tema)
    fondo_portada(rr / FONDO_PORTADA)
    w(d / "version.json", json.dumps({"$schema": f"{SCH}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2))
    w(d / "report.json", json.dumps({
        "$schema": f"{SCH}/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": BASE_THEME, "reportVersionAtImport": {"visual": "2.4.0", "report": "3.0.0", "page": "2.3.0"},
                          "type": "SharedResources"},
            "customTheme": {"name": TEMA_ARCHIVO, "reportVersionAtImport": {"visual": "2.4.0", "report": "3.0.0", "page": "2.3.0"},
                            "type": "RegisteredResources"}},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": TEMA_ARCHIVO, "path": TEMA_ARCHIVO, "type": "CustomTheme"},
                       {"name": FONDO_PORTADA, "path": FONDO_PORTADA, "type": "Image"}]}],
        # panel de filtros nativo oculto: los filtros viven en el cajón de cada página
        "objects": {"outspacePane": [{"properties": {"expanded": lit(False), "visible": lit(False)}}]},
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True},
    }, indent=2))
    P = paginas()
    w(d / "pages" / "pages.json", json.dumps({"$schema": f"{SCH}/pagesMetadata/1.0.0/schema.json",
                                              "pageOrder": [p.nombre for p in P], "activePageName": P[0].nombre}, indent=2))
    marcadores = []
    for p in P:
        pd_ = d / "pages" / p.nombre
        page = {"$schema": f"{SCH}/page/2.0.0/schema.json", "name": p.nombre, "displayName": p.display,
                "displayOption": "FitToPage", "height": p.alto, "width": p.ancho, **p.extra_page}
        if p.page_objects:
            page["objects"] = p.page_objects
        if p.interacciones:
            page["visualInteractions"] = p.interacciones
        w(pd_ / "page.json", json.dumps(page, indent=2, ensure_ascii=False))
        for v in p.visuales:
            w(pd_ / "visuals" / v["name"] / "visual.json", json.dumps(v, indent=2, ensure_ascii=False))
        for bid, nom, grupo, hijos, oculto in p.marcadores:
            marcadores.append(bid)
            w(d / "bookmarks" / f"{bid}.bookmark.json", json.dumps({
                "$schema": f"{SCH}/bookmark/1.4.0/schema.json", "displayName": nom, "name": bid,
                "options": {"targetVisualNames": [grupo, *hijos], "suppressData": True,
                            "applyOnlyToTargetVisuals": True, "suppressActiveSection": True},
                "explorationState": {"version": "1.3", "activeSection": p.nombre, "sections": {p.nombre: {
                    "visualContainers": {h: ({"singleVisual": {"display": {"mode": "hidden"}}} if oculto else {})
                                         for h in hijos},
                    "visualContainerGroups": {grupo: {"isHidden": oculto}}}}}}, indent=2, ensure_ascii=False))
    w(d / "bookmarks" / "bookmarks.json", json.dumps({"$schema": f"{SCH}/bookmarksMetadata/1.0.0/schema.json",
                                                      "items": [{"name": b} for b in marcadores]}, indent=2))
    return P


def w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    import subprocess
    if "PBIDesktop.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
        raise SystemExit("Cerrá Power BI Desktop antes de regenerar (bloquea pbip/).")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    w(OUT / f"{NAME}.pbip", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": RP}}], "settings": {"enableAutoRecovery": True}}, indent=2))
    w(OUT / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    escribir_modelo()
    P = escribir_reporte()
    nv = sum(len(p.visuales) for p in P)
    print(f"OK: {OUT / (NAME + '.pbip')}  |  {len(MEDIDAS)} medidas, {len(P)} páginas, {nv} visuales")


if __name__ == "__main__":
    main()
