"""
ATLAS | BSI Transporte EEUU
Genera el proyecto Power BI (PBIP): modelo semántico TMDL + reporte PBIR + tema ATLAS.

Uso: python -I 03_generar_pbip.py
Salida: ../pbip/BSI_Transporte_EEUU.pbip  (abrir con Power BI Desktop)
"""
import json
import shutil
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "pbip"
NAME = "BSI_Transporte_EEUU"
DATA_PATH = str(BASE / "data") + "\\"
PBI_THEMES = Path(r"C:\Program Files\Microsoft Power BI Desktop\bin\WebView2Resources\minerva\sharedresources\BaseThemes")
BASE_THEME = "CY26SU02"

# ---------------------------------------------------------------- paleta ATLAS
AZUL = "#1D1631"     # tinta ATLAS (banda, títulos)
VIOLETA = "#5B3F99"  # acento ATLAS
LILA = "#B9A6E6"
TURQ = "#10B981"     # bueno (semáforo: ≥80% a tiempo)
AMBAR = "#F59E0B"    # neutro (75–80%)
ROJO = "#EF4444"     # malo (<75%)
GRIS = "#6B6480"
FONDO = "#F3F4F6"    # lienzo
FILA_ALT = "#F9FAFB" # filas alternas de tablas
BORDE = "#E5E7EB"
# mapa de calor divergente azul → claro → naranja (apto daltónicos)
CALOR = ["#2166AC", "#67A9CF", "#D1E5F0", "#FDDBC7", "#F4A15D", "#D9600F"]
TEMA_ARCHIVO = "ATLAS_Theme.json"
PALETA = [VIOLETA, TURQ, AMBAR, "#1F4E9C", ROJO, "#7A5FB5", "#9A93AD", "#E06C3C", AZUL, GRIS]

SM = f"{NAME}.SemanticModel"
RP = f"{NAME}.Report"


def gid():
    return str(uuid.uuid4())


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
    expr_lines = expr.strip().split("\n")
    if len(expr_lines) == 1:
        head = f"\tmeasure {q(name)} = {expr_lines[0]}"
    else:
        head = f"\tmeasure {q(name)} =\n" + "\n".join("\t\t\t" + ln for ln in expr_lines)
    lines = [head]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    if folder:
        lines.append(f"\t\tdisplayFolder: {folder}")
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
    # --- Patrones (fPatrones: mes × aerolínea × día × hora)
    ("P Vuelos", "SUM ( fPatrones[Vuelos] )", "#,0", "5 Patrones", None),
    ("P % Demorados",
     "DIVIDE (\n    SUM ( fPatrones[LlegadasDemoradas] ),\n"
     "    SUM ( fPatrones[Vuelos] ) - SUM ( fPatrones[Cancelados] ) - SUM ( fPatrones[Desviados] )\n)",
     "0.0%", "5 Patrones", "% de llegadas demoradas según día y hora programada"),
    ("P % A Tiempo", "IF ( NOT ISBLANK ( [P % Demorados] ), 1 - [P % Demorados] )", "0.0%", "5 Patrones", None),
    ("P % Cancelados", "DIVIDE ( SUM ( fPatrones[Cancelados] ), [P Vuelos] )", "0.00%", "5 Patrones", None),
    # --- Detalle
    ("D Vuelos", "COUNTROWS ( fDetalle )", "#,0", "6 Detalle", None),
    ("Texto Detalle",
     "\"Vuelos de \" & FORMAT ( MAX ( fDetalle[Fecha] ), \"mmmm yyyy\" )",
     None, "6 Detalle", None),
    # --- Formato y textos
    ("Color Puntualidad",
     f"VAR v = [% A Tiempo]\nRETURN\n    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v >= 0.80, \"{TURQ}\", v >= 0.75, \"{AMBAR}\", \"{ROJO}\" )",
     None, "9 Formato", "Semáforo de puntualidad: verde ≥80%, ámbar 75–80%, rojo <75%"),
    ("Color % A Tiempo", "[Color Puntualidad]",
     None, "9 Formato", "Semáforo (alias de Color Puntualidad): verde ≥80%, ámbar 75–80%, rojo <75%"),
    ("Color P % A Tiempo",
     f"VAR v = [P % A Tiempo]\nRETURN\n    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v >= 0.80, \"{TURQ}\", v >= 0.75, \"{AMBAR}\", \"{ROJO}\" )",
     None, "9 Formato", "Semáforo sobre fPatrones: verde ≥80%, ámbar 75–80%, rojo <75%"),
    ("Color % Demorados",
     "VAR v = [P % Demorados]\nRETURN\n    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (),\n"
     f"        v < 0.12, \"{CALOR[0]}\", v < 0.16, \"{CALOR[1]}\", v < 0.20, \"{CALOR[2]}\",\n"
     f"        v < 0.24, \"{CALOR[3]}\", v < 0.28, \"{CALOR[4]}\", \"{CALOR[5]}\" )",
     None, "9 Formato", "Mapa de calor divergente azul → claro → naranja (apto daltónicos): azul = pocas demoras"),
    ("Color Texto % Demorados",
     f"VAR v = [P % Demorados]\nRETURN\n    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v < 0.16 || v >= 0.28, \"#FFFFFF\", \"{AZUL}\" )",
     None, "9 Formato", "Texto oscuro sobre celdas claras del mapa de calor, blanco sobre las oscuras"),
    ("Color Demora Llegada",
     "VAR v = MAX ( fDetalle[DemoraLlegadaMin] )\nRETURN\n    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v > 60, \"#FDE2E2\", v <= 0, \"#D1FAE5\", BLANK () )",
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
                   *[(c, "int64", NUM) for c in ["Vuelos", "Cancelados", "Desviados", "LlegadasDemoradas"]]],
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
    "dAerolinea": ([("AerolineaCod", "string", {"key": True}), ("Aerolinea", "string"), ("TipoAerolinea", "string")],
                   "dAerolinea.parquet"),
    "dOrigen": None, "dDestino": None,
    "dDiaSemana": ([("DiaSemanaNum", "int64", {**H, "key": True}), ("DiaSemana", "string", {"sort_by": "DiaSemanaNum"})],
                   "dDiaSemana.parquet"),
    "dHora": ([("HoraProgramada", "int64", {"fmt": "0", "key": True}), ("HoraTexto", "string"),
               ("FranjaOrden", "int64", H), ("FranjaHoraria", "string", {"sort_by": "FranjaOrden"})], "dHora.parquet"),
    "dCausaCancelacion": ([("CodigoCancelacion", "string", {"key": True, "hidden": True}),
                           ("CausaCancelacion", "string")], "dCausaCancelacion.parquet"),
}
TABLAS = list(TABLAS_DEF)

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
    s += [measure(n, e, f, d, desc) for n, e, f, d, desc in MEDIDAS]
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
             f"annotation PBI_QueryOrder = {json.dumps(['RutaDatos'] + TABLAS, ensure_ascii=False)}", ""]
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
        elif t in ("dOrigen", "dDestino"):
            txt = tmdl_aeropuerto(t[1:])
        else:
            txt = tabla(t, *spec)
        w(d / "tables" / f"{t}.tmdl", txt)


# =============================================================== REPORTE (PBIR)
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


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
    "Δ % A Tiempo vs AA": "Δ vs año ant. (pp)", "Demora Promedio de Demorados": "Demora media demorados",
    "% Causa Controlable": "% controlable", "Ranking Aerolínea": "Ranking", "Taxi Salida Promedio": "Taxi salida (min)",
    "Vuelos Demorados": "Vuelos demorados", "Vuelos Cancelados": "Vuelos cancelados",
    "Demora Promedio Llegada": "Demora media llegada",
    **{f"Min Demora {c}": ETIQ_CAUSA[c] for c, _ in CAUSAS}, **{f"% Causa {c}": ETIQ_CAUSA[c] for c, _ in CAUSAS},
    "Δ % A Tiempo 12M": "Δ 12M (pp)", "Cancelados por Causa": "Vuelos cancelados", "FechaMes": "Mes",
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
    col = {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
    return {"field": {"Aggregation": {"Expression": col, "Function": 1}},
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


def titulo(texto):
    return {"title": [{"properties": {"show": lit(True), "text": lit(texto), "fontColor": {"solid": {"color": lit(AZUL)}},
                                      "fontSize": lit(11), "bold": lit(True)}}]}


def contenedor(extra=None):
    o = {"background": [{"properties": {"show": lit(True), "color": {"solid": {"color": lit("#FFFFFF")}}}}],
         "border": [{"properties": {"show": lit(True), "color": {"solid": {"color": lit(BORDE)}}, "radius": lit(10)}}],
         "dropShadow": [{"properties": {"show": lit(True), "color": {"solid": {"color": lit(AZUL)}}, "position": lit("Outer"),
                                        "preset": lit("Custom"), "transparency": lit(88), "shadowBlur": lit(10),
                                        "shadowDistance": lit(3), "shadowSpread": lit(0), "angle": lit(90)}}]}
    if extra:
        o.update(extra)
    return o


GRAFICOS = {"lineChart", "clusteredBarChart", "clusteredColumnChart", "columnChart", "barChart",
            "hundredPercentStackedBarChart"}
BARRAS = {"clusteredBarChart", "clusteredColumnChart"}
MAPA_ZOOM = {"p1resumen": 2.3, "p3aeropuertos": 3.2}


class Pagina:
    def __init__(self, nombre, display):
        self.nombre, self.display, self.visuales, self.z = nombre, display, [], 0

    def add(self, vtype, x, y, wd, h, roles=None, title=None, objects=None, sort=None, extra_vco=None):
        self.z += 1
        v = {"visualType": vtype, "drillFilterOtherVisuals": True}
        if roles:
            v["query"] = {"queryState": {r: {"projections": p} for r, p in roles.items()}}
            if sort:
                v["query"]["sortDefinition"] = {"sort": [{"field": sort[0]["field"], "direction": sort[1]}],
                                                "isDefaultSort": False}
        objects = dict(objects or {})
        if vtype in GRAFICOS:
            objects.setdefault("categoryAxis", [{"properties": {"showAxisTitle": lit(False)}}])
            objects.setdefault("valueAxis", [{"properties": {"showAxisTitle": lit(False)}}])
        if vtype in BARRAS and "labels" not in objects:
            objects["labels"] = [{"properties": {"show": lit(True), "fontSize": lit(8)}}]
        if vtype == "tableEx":
            objects.setdefault("values", [{"properties": {"fontSize": lit(10)}}])
            objects.setdefault("columnHeaders", [{"properties": {"fontSize": lit(10)}}])
            objects.setdefault("total", [{"properties": {"fontSize": lit(10)}}])
        if vtype == "azureMap":
            objects.setdefault("mapControls", [{"properties": {
                "autoZoom": lit(False), "zoom": lit(MAPA_ZOOM.get(self.nombre, 3.2)),
                "centerLatitude": lit(38.5), "centerLongitude": lit(-96.5), "showStylePicker": lit(False)}}])
            objects.setdefault("bubbleLayer", [{"properties": {"maxRadius": lit(16)}}])
        if objects:
            v["objects"] = objects
        vco = contenedor(titulo(title) if title else {"title": [{"properties": {"show": lit(False)}}]})
        if extra_vco:
            vco.update(extra_vco)
        v["visualContainerObjects"] = vco
        self.visuales.append({
            "$schema": f"{SCH}/visualContainer/2.4.0/schema.json",
            "name": f"{self.nombre}_{self.z:02d}_{vtype}",
            "position": {"x": x, "y": y, "z": self.z * 1000, "width": wd, "height": h, "tabOrder": self.z * 1000},
            "visual": v,
        })

    def texto(self, x, y, wd, h, runs):
        self.z += 1
        self.visuales.append({
            "$schema": f"{SCH}/visualContainer/2.4.0/schema.json",
            "name": f"{self.nombre}_{self.z:02d}_textbox",
            "position": {"x": x, "y": y, "z": self.z * 1000, "width": wd, "height": h, "tabOrder": self.z * 1000},
            "visual": {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [
                {"textRuns": [{"value": t, "textStyle": st} for t, st in runs]}]}}]},
                       "visualContainerObjects": {"background": [{"properties": {"show": lit(False)}}]}},
        })

    def encabezado(self, subtitulo, slicers=None, periodo="Texto Período", subtitulo_medida=None):
        self.z += 1
        # banda superior
        self.visuales.append({
            "$schema": f"{SCH}/visualContainer/2.4.0/schema.json", "name": f"{self.nombre}_00_banda",
            "position": {"x": 0, "y": 0, "z": 0, "width": 1280, "height": 64, "tabOrder": 0},
            "visual": {"visualType": "shape", "objects": {
                "shape": [{"properties": {"tileShape": lit("rectangle")}}],
                "fill": [{"properties": {"fillColor": {"solid": {"color": lit(AZUL)}}, "transparency": lit(0)}}],
                "outline": [{"properties": {"show": lit(False)}}]}}})
        self.texto(20, 6, 520, 52, [
            ("ATLAS  ", {"fontWeight": "bold", "fontSize": "20pt", "color": LILA}),
            ("|  BSI Transporte EEUU", {"fontWeight": "bold", "fontSize": "16pt", "color": "#FFFFFF"})])
        if subtitulo_medida:  # subtítulo dinámico (tarjeta transparente con una medida de texto)
            self.add("card", 500, 8, 480, 48, {"Values": [M(subtitulo_medida)]}, objects={
                "labels": [{"properties": {"color": {"solid": {"color": lit("#E4DFEE")}}, "fontSize": lit(12)}}],
                "categoryLabels": [{"properties": {"show": lit(False)}}]},
                extra_vco={"background": [{"properties": {"show": lit(False)}}],
                           "border": [{"properties": {"show": lit(False)}}],
                           "dropShadow": [{"properties": {"show": lit(False)}}]})
            self.visuales[-1]["name"] = f"{self.nombre}_{self.z:02d}_titulo"
        else:
            self.texto(560, 14, 420, 40, [(subtitulo, {"fontSize": "12pt", "color": "#C9C2DB"})])
        # tarjeta con período dinámico
        self.add("card", 990, 8, 280, 48, {"Values": [M(periodo)]}, objects={
            "labels": [{"properties": {"color": {"solid": {"color": lit("#FFFFFF")}}, "fontSize": lit(11)}}],
            "categoryLabels": [{"properties": {"show": lit(False)}}]},
            extra_vco={"background": [{"properties": {"show": lit(False)}}],
                       "border": [{"properties": {"show": lit(False)}}],
                       "dropShadow": [{"properties": {"show": lit(False)}}]})
        # segmentadores
        y = 72
        for i, (ent, prop, tit) in enumerate(slicers or SLICERS_STD):
            self.add("slicer", 20 + i * 250, 70, 240, 60, {"Values": [C(ent, prop)]}, objects={
                "data": [{"properties": {"mode": lit("Dropdown")}}],
                "header": [{"properties": {"show": lit(True), "text": lit(tit), "textSize": lit(9),
                                           "fontColor": {"solid": {"color": lit(GRIS)}}}}],
                "items": [{"properties": {"textSize": lit(9)}}]},
                extra_vco={"padding": [{"properties": {"top": lit(2), "bottom": lit(2), "left": lit(6), "right": lit(6)}}]})

    def pie(self):
        self.add("card", 20, 696, 700, 22, {"Values": [M("Texto Fuente")]}, objects={
            "labels": [{"properties": {"color": {"solid": {"color": lit(GRIS)}}, "fontSize": lit(8)}}],
            "categoryLabels": [{"properties": {"show": lit(False)}}]},
            extra_vco={"background": [{"properties": {"show": lit(False)}}], "border": [{"properties": {"show": lit(False)}}],
                       "dropShadow": [{"properties": {"show": lit(False)}}]})


def kpis(p, y, medidas):
    n = len(medidas)
    wd = (1240 - (n - 1) * 12) // n
    for i, (m, tit) in enumerate(medidas):
        p.add("card", 20 + i * (wd + 12), y, wd, 92, {"Values": [M(m)]}, title=tit, objects={
            "labels": [{"properties": {"color": {"solid": {"color": lit(AZUL)}}, "fontSize": lit(22),
                                       "labelDisplayUnits": lit(1)}}],
            "categoryLabels": [{"properties": {"show": lit(False)}}]})


def barras_color(medida_color="Color Puntualidad"):
    return {"dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {"Measure": {
        "Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": medida_color}}}}}},
        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]}


def color_medida(medida):
    return {"solid": {"color": {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": medida}}}}}


def barra_datos(query_ref, color):
    """Barras de datos en una columna de tabla."""
    return {"properties": {"dataBars": {"positiveColor": {"solid": {"color": lit(color)}},
                                        "negativeColor": {"solid": {"color": lit("#FCA5A5")}},
                                        "axisColor": {"solid": {"color": lit("#9CA3AF")}},
                                        "reverseDirection": lit(False), "hideText": lit(False)}},
            "selector": {"metadata": query_ref}}


SLICERS_STD = [("dMes", "Anio", "Año"), ("dMes", "Mes", "Mes"), ("dAerolinea", "Aerolinea", "Aerolínea"),
               ("dOrigen", "OrigenEstado", "Estado de origen"), ("dOrigen", "OrigenCodigo", "Aeropuerto de origen")]
SLICERS_PATRON = [("dMes", "Anio", "Año"), ("dMes", "Mes", "Mes"), ("dAerolinea", "Aerolinea", "Aerolínea"),
                  ("dAerolinea", "TipoAerolinea", "Tipo de aerolínea")]
SLICERS_DETALLE = [("dAerolinea", "Aerolinea", "Aerolínea"), ("dOrigen", "OrigenCodigo", "Aeropuerto de origen"),
                   ("dDestino", "DestinoCodigo", "Aeropuerto de destino"),
                   ("dCausaCancelacion", "CausaCancelacion", "Causa de cancelación"), ("dHora", "FranjaHoraria", "Franja")]


def paginas():
    P = []
    # 1 RESUMEN ---------------------------------------------------------------
    p = Pagina("p1resumen", "Resumen")
    p.encabezado("Resumen ejecutivo de puntualidad", subtitulo_medida="Titulo Dinamico")
    kpis(p, 136, [("Vuelos", "Vuelos"), ("% A Tiempo", "% a tiempo"), ("Δ % A Tiempo 12M", "Δ últimos 12 meses (pp)"),
                  ("% Cancelados", "% cancelados"), ("Demora Promedio de Demorados", "Demora media de demorados"),
                  ("Horas de Demora", "Horas de demora")])
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

    # 2 AEROLÍNEAS ------------------------------------------------------------
    p = Pagina("p2aerolineas", "Aerolíneas")
    p.encabezado("Comparativo de aerolíneas")
    p.add("tableEx", 20, 136, 1240, 286, {"Values": [
        C("dAerolinea", "Aerolinea"), C("dAerolinea", "TipoAerolinea"), M("Ranking Aerolínea"), M("Vuelos"),
        M("% A Tiempo"), M("Δ % A Tiempo 12M"), M("% Cancelados"), M("Demora Promedio de Demorados"),
        M("% Causa Controlable"), M("Taxi Salida Promedio")]}, title="Tabla de desempeño (ordenar por columna)",
        sort=(M("Ranking Aerolínea"), "Ascending"), objects={"columnFormatting": [
            barra_datos("Medidas.Vuelos", "#B9A8DC"), barra_datos("Medidas.% A Tiempo", "#A7E3CB")]})
    p.add("lineChart", 20, 432, 470, 258, {"Category": [C("dMes", "FechaMes")],
                                           "Series": [C("dAerolinea", "TipoAerolinea")], "Y": [M("% A Tiempo")]},
          title="% a tiempo: troncales vs regionales vs low cost", sort=(C("dMes", "FechaMes"), "Ascending"))
    p.add("clusteredBarChart", 502, 432, 374, 258, {"Category": [C("dAerolinea", "Aerolinea")], "Y": [M("Vuelos")]},
          title="Vuelos por aerolínea", sort=(M("Vuelos"), "Descending"))
    p.add("clusteredBarChart", 888, 432, 372, 258, {"Category": [C("dAerolinea", "Aerolinea")], "Y": [M("% Cancelados")]},
          title="% cancelados por aerolínea", sort=(M("% Cancelados"), "Descending"))
    p.pie()
    P.append(p)

    # 3 AEROPUERTOS Y RUTAS ---------------------------------------------------
    p = Pagina("p3aeropuertos", "Aeropuertos y rutas")
    p.encabezado("Dónde se concentran las demoras")
    p.add("azureMap", 20, 136, 620, 554, {"Category": [C("dOrigen", "OrigenCodigo")], "Y": [PROM("dOrigen", "OrigenLatitud")],
                                     "X": [PROM("dOrigen", "OrigenLongitud")], "Size": [M("Vuelos Demorados")],
                                     "Tooltips": [M("Vuelos"), M("% A Tiempo"), M("Demora Promedio de Demorados")]},
          title="Vuelos demorados por aeropuerto de origen")
    p.add("tableEx", 652, 136, 608, 272, {"Values": [
        C("dOrigen", "OrigenCodigo"), C("dOrigen", "OrigenCiudad"), C("dOrigen", "OrigenEstadoCod"), M("Vuelos"),
        M("% A Tiempo"), M("% Cancelados"), M("Taxi Salida Promedio")]},
          title="Aeropuertos de origen (ordenar por columna)", sort=(M("Vuelos"), "Descending"))
    p.add("tableEx", 652, 418, 608, 272, {"Values": [
        C("dOrigen", "OrigenCodigo"), C("dDestino", "DestinoCodigo"), M("Vuelos"), M("% A Tiempo"), M("% Cancelados"),
        M("Demora Promedio de Demorados")]},
          title="Rutas (origen → destino)", sort=(M("Vuelos"), "Descending"))
    p.pie()
    P.append(p)

    # 4 CAUSAS ----------------------------------------------------------------
    p = Pagina("p4causas", "Causas de demora")
    p.encabezado("Por qué se demoran y cancelan los vuelos")
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
    p.encabezado("Cuándo conviene volar", SLICERS_PATRON)
    p.add("pivotTable", 20, 136, 1240, 226, {"Rows": [C("dDiaSemana", "DiaSemana")], "Columns": [C("dHora", "HoraTexto")],
                                             "Values": [M("P % Demorados")]},
          title="% de vuelos demorados por día y hora programada de salida",
          objects={"values": [{"properties": {
              "backColor": {"solid": {"color": {"expr": {"Measure": {
                  "Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": "Color % Demorados"}}}}},
              "fontColor": color_medida("Color Texto % Demorados")},
              "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "Medidas.P % Demorados"}}]})
    p.add("lineChart", 20, 372, 610, 318, {"Category": [C("dMes", "Mes")], "Series": [C("dMes", "Anio")],
                                           "Y": [M("% A Tiempo")]},
          title="Estacionalidad: % a tiempo por mes y año", sort=(C("dMes", "Mes"), "Ascending"))
    p.add("clusteredColumnChart", 642, 372, 300, 318, {"Category": [C("dHora", "FranjaHoraria")], "Y": [M("P % A Tiempo")]},
          title="% a tiempo por franja", objects=barras_color("Color P % A Tiempo"),
          sort=(C("dHora", "FranjaHoraria"), "Ascending"))
    p.add("clusteredColumnChart", 954, 372, 306, 318, {"Category": [C("dDiaSemana", "DiaSemana")], "Y": [M("P % Cancelados")]},
          title="% cancelados por día", sort=(C("dDiaSemana", "DiaSemana"), "Ascending"))
    p.pie()
    P.append(p)

    # 6 DETALLE ---------------------------------------------------------------
    p = Pagina("p6detalle", "Detalle de vuelos")
    p.encabezado("Consulta vuelo por vuelo", SLICERS_DETALLE, periodo="Texto Detalle")
    p.add("tableEx", 20, 136, 1240, 554, {"Values": [
        C("fDetalle", "Fecha"), C("dAerolinea", "Aerolinea"), C("fDetalle", "NroVuelo"), C("fDetalle", "Ruta"),
        C("dHora", "HoraTexto"), C("fDetalle", "DemoraSalidaMin"), C("fDetalle", "DemoraLlegadaMin"),
        C("fDetalle", "Cancelado"), C("dCausaCancelacion", "CausaCancelacion"), C("fDetalle", "Desviado"),
        C("fDetalle", "DistanciaMillas")]}, title="Vuelos", sort=(C("fDetalle", "DemoraLlegadaMin"), "Descending"),
        objects={"values": [{"properties": {"fontSize": lit(10)}},
                            {"properties": {"backColor": color_medida("Color Demora Llegada")},
                             "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                          "metadata": "fDetalle.DemoraLlegadaMin"}}]})
    p.pie()
    P.append(p)
    return P


TEMA = {
    "name": "ATLAS v2",
    "dataColors": PALETA,
    "foreground": AZUL, "foregroundNeutralSecondary": GRIS, "foregroundNeutralTertiary": "#8A97A6",
    "background": "#FFFFFF", "backgroundLight": FONDO, "backgroundNeutral": BORDE,
    "tableAccent": VIOLETA, "good": TURQ, "neutral": AMBAR, "bad": ROJO,
    "maximum": ROJO, "center": AMBAR, "minimum": TURQ,
    "textClasses": {
        "title": {"fontFace": "Segoe UI Semibold", "color": AZUL, "fontSize": 11},
        "callout": {"fontFace": "Segoe UI Semibold", "color": AZUL, "fontSize": 24},
        "label": {"fontFace": "Segoe UI", "color": GRIS, "fontSize": 9},
        "header": {"fontFace": "Segoe UI Semibold", "color": AZUL, "fontSize": 12},
    },
    "visualStyles": {
        "page": {"*": {"background": [{"color": {"solid": {"color": FONDO}}, "transparency": 0}],
                       "outspace": [{"color": {"solid": {"color": FONDO}}}]}},
        "tableEx": {"*": {"columnHeaders": [{"backColor": {"solid": {"color": AZUL}}, "fontColor": {"solid": {"color": "#FFFFFF"}}}],
                          "values": [{"backColorSecondary": {"solid": {"color": FILA_ALT}}}]}},
        "pivotTable": {"*": {"columnHeaders": [{"backColor": {"solid": {"color": AZUL}}, "fontColor": {"solid": {"color": "#FFFFFF"}}}],
                             "rowHeaders": [{"backColor": {"solid": {"color": AZUL}}, "fontColor": {"solid": {"color": "#FFFFFF"}}}]}},
        # tarjetas blancas con borde redondeado y sombra sutil
        "*": {"*": {"background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
                    "border": [{"show": True, "color": {"solid": {"color": BORDE}}, "radius": 10}],
                    "dropShadow": [{"show": True, "color": {"solid": {"color": AZUL}}, "position": "Outer", "preset": "Custom",
                                    "transparency": 88, "shadowBlur": 10, "shadowDistance": 3, "shadowSpread": 0, "angle": 90}]}},
        # textos, formas e imágenes sin tarjeta
        **{vt: {"*": {"background": [{"show": False}], "border": [{"show": False}], "dropShadow": [{"show": False}]}}
           for vt in ("textbox", "shape", "basicShape", "image", "actionButton")},
    },
}


def escribir_reporte():
    r = OUT / RP
    d = r / "definition"
    w(r / "definition.pbir", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{SM}"}}}, indent=2))
    # recursos de tema
    sr = r / "StaticResources" / "SharedResources" / "BaseThemes"
    sr.mkdir(parents=True, exist_ok=True)
    shutil.copy(PBI_THEMES / f"{BASE_THEME}.json", sr / f"{BASE_THEME}.json")
    rr = r / "StaticResources" / "RegisteredResources"
    rr.mkdir(parents=True, exist_ok=True)
    w(rr / TEMA_ARCHIVO, json.dumps(TEMA, indent=2, ensure_ascii=False))
    w(BASE / TEMA_ARCHIVO, json.dumps(TEMA, indent=2, ensure_ascii=False))
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
             "items": [{"name": TEMA_ARCHIVO, "path": TEMA_ARCHIVO, "type": "CustomTheme"}]}],
        # panel de filtros nativo oculto para los lectores (los segmentadores están en el lienzo)
        "objects": {"outspacePane": [{"properties": {"expanded": lit(False), "visible": lit(False)}}]},
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True},
    }, indent=2))
    P = paginas()
    w(d / "pages" / "pages.json", json.dumps({"$schema": f"{SCH}/pagesMetadata/1.0.0/schema.json",
                                              "pageOrder": [p.nombre for p in P], "activePageName": P[0].nombre}, indent=2))
    for p in P:
        pd_ = d / "pages" / p.nombre
        w(pd_ / "page.json", json.dumps({"$schema": f"{SCH}/page/2.0.0/schema.json", "name": p.nombre,
                                         "displayName": p.display, "displayOption": "FitToPage",
                                         "height": 720, "width": 1280}, indent=2, ensure_ascii=False))
        for v in p.visuales:
            w(pd_ / "visuals" / v["name"] / "visual.json", json.dumps(v, indent=2, ensure_ascii=False))
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
