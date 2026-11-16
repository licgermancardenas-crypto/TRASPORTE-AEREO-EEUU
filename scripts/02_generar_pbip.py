"""
ATLAS | BSI Transporte EEUU
Genera el proyecto Power BI (PBIP): modelo semántico TMDL + reporte PBIR + tema ATLAS.

Uso: python -I 02_generar_pbip.py
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
TURQ = "#2E9C8F"     # bueno
AMBAR = "#E0A526"    # neutro
ROJO = "#C8102E"     # malo
GRIS = "#6B6480"
FONDO = "#F4F1F9"
BORDE = "#E4DFEE"
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

MEDIDAS = [
    # --- Volumen
    ("Vuelos", "COUNTROWS ( fVuelos )", "#,0", "1 Volumen", "Vuelos programados reportados a BTS"),
    ("Vuelos Cancelados", "SUM ( fVuelos[Cancelado] )", "#,0", "1 Volumen", None),
    ("Vuelos Desviados", "SUM ( fVuelos[Desviado] )", "#,0", "1 Volumen", None),
    ("Vuelos Operados", "[Vuelos] - [Vuelos Cancelados] - [Vuelos Desviados]", "#,0", "1 Volumen",
     "Vuelos que llegaron a destino (base para puntualidad, criterio BTS)"),
    ("Vuelos Demorados", "SUM ( fVuelos[LlegadaDemorada15] )", "#,0", "1 Volumen",
     "Vuelos con llegada 15+ minutos tarde"),
    ("Vuelos a Tiempo", "[Vuelos Operados] - [Vuelos Demorados]", "#,0", "1 Volumen", None),
    ("Millas Voladas", "SUM ( fVuelos[DistanciaMillas] )", "#,0", "1 Volumen", None),
    # --- Puntualidad
    ("% A Tiempo", "DIVIDE ( [Vuelos a Tiempo], [Vuelos Operados] )", "0.0%", "2 Puntualidad",
     "Llegadas con menos de 15 min de demora / vuelos operados"),
    ("% Demorados", "DIVIDE ( [Vuelos Demorados], [Vuelos Operados] )", "0.0%", "2 Puntualidad", None),
    ("% Cancelados", "DIVIDE ( [Vuelos Cancelados], [Vuelos] )", "0.00%", "2 Puntualidad", None),
    ("% Desviados", "DIVIDE ( [Vuelos Desviados], [Vuelos] )", "0.00%", "2 Puntualidad", None),
    ("% Salidas Demoradas", "DIVIDE ( SUM ( fVuelos[SalidaDemorada15] ), [Vuelos] - [Vuelos Cancelados] )", "0.0%",
     "2 Puntualidad", None),
    ("Demora Promedio Llegada", "AVERAGE ( fVuelos[DemoraLlegadaMin] )", "#,0.0 \"min\"", "2 Puntualidad",
     "Promedio de todos los vuelos operados (negativo = llegó antes)"),
    ("Demora Promedio Salida", "AVERAGE ( fVuelos[DemoraSalidaMin] )", "#,0.0 \"min\"", "2 Puntualidad", None),
    ("Demora Promedio de Demorados",
     "CALCULATE ( AVERAGE ( fVuelos[DemoraLlegadaMin] ), fVuelos[LlegadaDemorada15] = 1 )",
     "#,0.0 \"min\"", "2 Puntualidad", "Demora media solo de los vuelos que llegaron 15+ min tarde"),
    ("Taxi Salida Promedio", "AVERAGE ( fVuelos[TaxiSalidaMin] )", "#,0.0 \"min\"", "2 Puntualidad", None),
    # --- Causas
    *[(f"Min Demora {c}", f"SUM ( fVuelos[{src}] )", "#,0", "3 Causas de demora", None) for c, src in CAUSAS],
    ("Min Demora Total", " + ".join(f"[Min Demora {c}]" for c, _ in CAUSAS), "#,0", "3 Causas de demora",
     "Minutos de demora atribuidos a alguna causa (vuelos 15+ min tarde)"),
    ("Horas de Demora", "DIVIDE ( [Min Demora Total], 60 )", "#,0", "3 Causas de demora", None),
    *[(f"% Causa {c}", f"DIVIDE ( [Min Demora {c}], [Min Demora Total] )", "0.0%", "3 Causas de demora", None)
      for c, _ in CAUSAS],
    ("% Causa Controlable",
     "DIVIDE ( [Min Demora Aerolínea] + [Min Demora Avión previo], [Min Demora Total] )", "0.0%",
     "3 Causas de demora", "Demoras atribuibles a la operación de la aerolínea (propia + avión previo)"),
    # --- Comparaciones
    ("Vuelos Año Anterior", "CALCULATE ( [Vuelos], SAMEPERIODLASTYEAR ( dCalendario[Fecha] ) )", "#,0",
     "4 Comparaciones", None),
    ("Var % Vuelos vs AA", "DIVIDE ( [Vuelos] - [Vuelos Año Anterior], [Vuelos Año Anterior] )", "+0.0%;-0.0%;0.0%",
     "4 Comparaciones", None),
    ("% A Tiempo Año Anterior", "CALCULATE ( [% A Tiempo], SAMEPERIODLASTYEAR ( dCalendario[Fecha] ) )", "0.0%",
     "4 Comparaciones", None),
    ("Δ % A Tiempo vs AA", "IF ( NOT ISBLANK ( [% A Tiempo Año Anterior] ), [% A Tiempo] - [% A Tiempo Año Anterior] )",
     "+0.0%;-0.0%;0.0%", "4 Comparaciones", "Diferencia en puntos porcentuales contra igual período del año anterior"),
    ("% A Tiempo Mes Anterior", "CALCULATE ( [% A Tiempo], DATEADD ( dCalendario[Fecha], -1, MONTH ) )", "0.0%",
     "4 Comparaciones", None),
    ("% A Tiempo Móvil 3M",
     "CALCULATE (\n    [% A Tiempo],\n    DATESINPERIOD ( dCalendario[Fecha], MAX ( dCalendario[Fecha] ), -3, MONTH )\n)",
     "0.0%", "4 Comparaciones", None),
    ("Ranking Aerolínea",
     "IF (\n    HASONEVALUE ( dAerolinea[Aerolinea] ),\n    RANKX ( ALLSELECTED ( dAerolinea[Aerolinea] ), [% A Tiempo], , DESC, DENSE )\n)",
     "0", "4 Comparaciones", "Posición por % a tiempo dentro de lo filtrado"),
    # --- Formato y textos
    ("Color % A Tiempo",
     f"VAR v = [% A Tiempo]\nRETURN\n    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v >= 0.80, \"{TURQ}\", v >= 0.72, \"{AMBAR}\", \"{ROJO}\" )",
     None, "5 Formato", "Semáforo: verde ≥80%, ámbar ≥72%, rojo debajo"),
    ("Color % Demorados",
     f"VAR v = [% Demorados]\nRETURN\n    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v < 0.15, \"{TURQ}\", v < 0.20, \"#7FB8A0\", v < 0.25, \"{AMBAR}\", v < 0.30, \"#E06C3C\", \"{ROJO}\" )",
     None, "5 Formato", "Escala para mapa de calor: <15% verde ... ≥30% rojo"),
    ("Texto Período",
     "\"Período: \" & FORMAT ( MIN ( dCalendario[Fecha] ), \"mmm yyyy\" ) & \" – \" & FORMAT ( MAX ( dCalendario[Fecha] ), \"mmm yyyy\" )",
     None, "5 Formato", None),
    ("Texto Fuente", "\"Fuente: BTS – On-Time Performance (transtats.bts.gov). Elaboración ATLAS.\"", None,
     "5 Formato", None),
]


def tmdl_fvuelos():
    s = ["table fVuelos", ""]
    s += [measure(n, e, f, d, desc) for n, e, f, d, desc in MEDIDAS]
    cols = [
        ("FechaKey", "int64", True), ("AerolineaCod", "string", True), ("NroVuelo", "int64", False),
        ("OrigenCod", "string", True), ("DestinoCod", "string", True), ("Ruta", "string", False),
        ("HoraProgramada", "int64", True), ("DemoraSalidaMin", "double", False),
        ("DemoraLlegadaMin", "double", False), ("SalidaDemorada15", "int64", True),
        ("LlegadaDemorada15", "int64", True), ("Cancelado", "int64", False), ("Desviado", "int64", False),
        ("CodigoCancelacion", "string", True), ("DistanciaMillas", "double", False),
        ("TiempoAireMin", "double", True), ("TaxiSalidaMin", "double", True), ("TaxiLlegadaMin", "double", True),
        *[(src, "double", True) for _, src in CAUSAS],
    ]
    for n, t, h in cols:
        summ = "sum" if t == "double" and not h else "none"
        s.append(col(n, t, hidden=h, summarize=summ, fmt="0" if t == "int64" else None))
    s.append(partition("fVuelos", parquet_m("fVuelos.parquet")))
    return "\n".join(s)


def tmdl_calendario():
    s = ["table dCalendario", "\tdataCategory: Time", ""]
    s += [
        col("Fecha", "dateTime", fmt="dd/mm/yyyy", key=True),
        col("FechaKey", "int64", hidden=True, fmt="0"),
        col("Anio", "int64", fmt="0"),
        col("MesNum", "int64", hidden=True, fmt="0"),
        col("Mes", "string", sort_by="MesNum"),
        col("MesCorto", "string", sort_by="MesNum"),
        col("AnioMes", "string"),
        col("AnioMesOrden", "int64", hidden=True, fmt="0"),
        col("Trimestre", "string"),
        col("DiaSemanaNum", "int64", hidden=True, fmt="0"),
        col("DiaSemana", "string", sort_by="DiaSemanaNum"),
        col("EsFinDeSemana", "boolean"),
        col("Temporada", "string"),
    ]
    s.append(partition("dCalendario", parquet_m(
        "dCalendario.parquet", ["Table.TransformColumnTypes({prev}, {{\"Fecha\", type date}})"])))
    return "\n".join(s)


def tmdl_aerolinea():
    s = ["table dAerolinea", "",
         col("AerolineaCod", "string", key=True), col("Aerolinea", "string"), col("TipoAerolinea", "string"),
         partition("dAerolinea", parquet_m("dAerolinea.parquet"))]
    return "\n".join(s)


def tmdl_aeropuerto(rol):
    t = f"d{rol}"
    s = [f"table {t}", "",
         col(f"{rol}Codigo", "string", key=True),
         col(f"{rol}Ciudad", "string", category="City"),
         col(f"{rol}EstadoCod", "string"),
         col(f"{rol}Estado", "string", category="StateOrProvince"),
         col(f"{rol}NombreAeropuerto", "string"),
         col(f"{rol}Latitud", "double", category="Latitude", fmt="0.0000"),
         col(f"{rol}Longitud", "double", category="Longitude", fmt="0.0000"),
         partition(t, parquet_m("dAeropuerto.parquet",
                                [f"Table.TransformColumnNames({{prev}}, each \"{rol}\" & _)"]))]
    return "\n".join(s)


def tmdl_hora():
    s = ["table dHora", "",
         col("HoraProgramada", "int64", fmt="0", key=True), col("HoraTexto", "string"),
         col("FranjaHoraria", "string"), partition("dHora", parquet_m("dHora.parquet"))]
    return "\n".join(s)


def tmdl_causa():
    s = ["table dCausaCancelacion", "",
         col("CodigoCancelacion", "string", key=True, hidden=True), col("CausaCancelacion", "string"),
         partition("dCausaCancelacion", parquet_m("dCausaCancelacion.parquet"))]
    return "\n".join(s)


RELS = [
    ("fVuelos.FechaKey", "dCalendario.FechaKey"),
    ("fVuelos.AerolineaCod", "dAerolinea.AerolineaCod"),
    ("fVuelos.OrigenCod", "dOrigen.OrigenCodigo"),
    ("fVuelos.DestinoCod", "dDestino.DestinoCodigo"),
    ("fVuelos.HoraProgramada", "dHora.HoraProgramada"),
    ("fVuelos.CodigoCancelacion", "dCausaCancelacion.CodigoCancelacion"),
]
TABLAS = ["fVuelos", "dCalendario", "dAerolinea", "dOrigen", "dDestino", "dHora", "dCausaCancelacion"]


def escribir_modelo():
    d = OUT / SM / "definition"
    (d / "tables").mkdir(parents=True, exist_ok=True)
    w(OUT / SM / "definition.pbism", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2))
    w(d / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: es-AR", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull",
             "", "annotation __PBI_TimeIntelligenceEnabled = 0", "",
             f"annotation PBI_QueryOrder = {json.dumps(['RutaDatos'] + TABLAS)}", ""]
    model += [f"ref table {t}" for t in TABLAS]
    w(d / "model.tmdl", "\n".join(model) + "\n")
    w(d / "expressions.tmdl",
      f'expression RutaDatos = "{DATA_PATH}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
      "\tannotation PBI_ResultType = Text\n")
    rel = []
    for f, t in RELS:
        rel += [f"relationship {uuid.uuid5(uuid.NAMESPACE_URL, f + t)}", f"\tfromColumn: {f}", f"\ttoColumn: {t}", ""]
    w(d / "relationships.tmdl", "\n".join(rel))
    w(d / "tables" / "fVuelos.tmdl", tmdl_fvuelos())
    w(d / "tables" / "dCalendario.tmdl", tmdl_calendario())
    w(d / "tables" / "dAerolinea.tmdl", tmdl_aerolinea())
    w(d / "tables" / "dOrigen.tmdl", tmdl_aeropuerto("Origen"))
    w(d / "tables" / "dDestino.tmdl", tmdl_aeropuerto("Destino"))
    w(d / "tables" / "dHora.tmdl", tmdl_hora())
    w(d / "tables" / "dCausaCancelacion.tmdl", tmdl_causa())


# =============================================================== REPORTE (PBIR)
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


def C(entity, prop):  # columna
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def M(prop, entity="fVuelos"):  # medida
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


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
         "border": [{"properties": {"show": lit(True), "color": {"solid": {"color": lit(BORDE)}}, "radius": lit(8)}}],
         "dropShadow": [{"properties": {"show": lit(False)}}]}
    if extra:
        o.update(extra)
    return o


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

    def encabezado(self, subtitulo):
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
        self.texto(560, 14, 420, 40, [(subtitulo, {"fontSize": "12pt", "color": "#C9C2DB"})])
        # tarjeta con período dinámico
        self.add("card", 990, 8, 280, 48, {"Values": [M("Texto Período")]}, objects={
            "labels": [{"properties": {"color": {"solid": {"color": lit("#FFFFFF")}}, "fontSize": lit(11)}}],
            "categoryLabels": [{"properties": {"show": lit(False)}}]},
            extra_vco={"background": [{"properties": {"show": lit(False)}}],
                       "border": [{"properties": {"show": lit(False)}}]})
        # segmentadores
        y = 72
        for i, (ent, prop, tit) in enumerate([("dCalendario", "Anio", "Año"), ("dCalendario", "Mes", "Mes"),
                                              ("dAerolinea", "Aerolinea", "Aerolínea"),
                                              ("dOrigen", "OrigenEstado", "Estado de origen"),
                                              ("dOrigen", "OrigenCodigo", "Aeropuerto de origen")]):
            self.add("slicer", 20 + i * 250, y, 240, 54, {"Values": [C(ent, prop)]}, objects={
                "data": [{"properties": {"mode": lit("Dropdown")}}],
                "header": [{"properties": {"show": lit(True), "text": lit(tit), "fontColor": {"solid": {"color": lit(GRIS)}}}}]})

    def pie(self):
        self.add("card", 20, 696, 700, 22, {"Values": [M("Texto Fuente")]}, objects={
            "labels": [{"properties": {"color": {"solid": {"color": lit(GRIS)}}, "fontSize": lit(8)}}],
            "categoryLabels": [{"properties": {"show": lit(False)}}]},
            extra_vco={"background": [{"properties": {"show": lit(False)}}], "border": [{"properties": {"show": lit(False)}}]})


def kpis(p, y, medidas):
    n = len(medidas)
    wd = (1240 - (n - 1) * 12) // n
    for i, (m, tit) in enumerate(medidas):
        p.add("card", 20 + i * (wd + 12), y, wd, 92, {"Values": [M(m)]}, title=tit, objects={
            "labels": [{"properties": {"color": {"solid": {"color": lit(AZUL)}}, "fontSize": lit(24)}}],
            "categoryLabels": [{"properties": {"show": lit(False)}}]})


def barras_color(medida_color="Color % A Tiempo"):
    return {"dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {"Measure": {
        "Expression": {"SourceRef": {"Entity": "fVuelos"}}, "Property": medida_color}}}}}},
        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]}


def paginas():
    P = []
    # 1 RESUMEN ---------------------------------------------------------------
    p = Pagina("p1resumen", "Resumen")
    p.encabezado("Resumen ejecutivo de puntualidad")
    kpis(p, 136, [("Vuelos", "Vuelos"), ("% A Tiempo", "% a tiempo"), ("Δ % A Tiempo vs AA", "Δ vs año anterior (pp)"),
                  ("% Cancelados", "% cancelados"), ("Demora Promedio de Demorados", "Demora media de demorados"),
                  ("Horas de Demora", "Horas de demora")])
    p.add("lineChart", 20, 240, 760, 220, {"Category": [C("dCalendario", "AnioMes")],
                                           "Y": [M("% A Tiempo"), M("% A Tiempo Móvil 3M")]},
          title="Evolución mensual del % a tiempo",
          sort=(C("dCalendario", "AnioMes"), "Ascending"))
    p.add("clusteredBarChart", 792, 240, 468, 450, {"Category": [C("dAerolinea", "Aerolinea")], "Y": [M("% A Tiempo")]},
          title="% a tiempo por aerolínea", objects=barras_color(), sort=(M("% A Tiempo"), "Descending"))
    p.add("map", 20, 470, 760, 220, {"Category": [C("dOrigen", "OrigenCodigo")], "Y": [C("dOrigen", "OrigenLatitud")],
                                     "X": [C("dOrigen", "OrigenLongitud")], "Size": [M("Vuelos")],
                                     "Tooltips": [M("% A Tiempo"), M("Demora Promedio Llegada")]},
          title="Aeropuertos de origen (tamaño = vuelos)")
    p.pie()
    P.append(p)

    # 2 AEROLÍNEAS ------------------------------------------------------------
    p = Pagina("p2aerolineas", "Aerolíneas")
    p.encabezado("Comparativo de aerolíneas")
    p.add("tableEx", 20, 136, 760, 300, {"Values": [
        C("dAerolinea", "Aerolinea"), C("dAerolinea", "TipoAerolinea"), M("Ranking Aerolínea"), M("Vuelos"),
        M("% A Tiempo"), M("Δ % A Tiempo vs AA"), M("% Cancelados"), M("Demora Promedio de Demorados"),
        M("% Causa Controlable")]}, title="Tabla de desempeño", sort=(M("Ranking Aerolínea"), "Ascending"))
    p.add("clusteredBarChart", 792, 136, 468, 300, {"Category": [C("dAerolinea", "Aerolinea")], "Y": [M("Vuelos")]},
          title="Vuelos por aerolínea", sort=(M("Vuelos"), "Descending"))
    p.add("lineChart", 20, 448, 760, 242, {"Category": [C("dCalendario", "AnioMes")],
                                           "Series": [C("dAerolinea", "TipoAerolinea")], "Y": [M("% A Tiempo")]},
          title="% a tiempo mensual: troncales vs regionales vs low cost",
          sort=(C("dCalendario", "AnioMes"), "Ascending"))
    p.add("clusteredBarChart", 792, 448, 468, 242, {"Category": [C("dAerolinea", "Aerolinea")], "Y": [M("% Cancelados")]},
          title="% cancelados por aerolínea", sort=(M("% Cancelados"), "Descending"))
    p.pie()
    P.append(p)

    # 3 AEROPUERTOS Y RUTAS ---------------------------------------------------
    p = Pagina("p3aeropuertos", "Aeropuertos y rutas")
    p.encabezado("Dónde se concentran las demoras")
    p.add("map", 20, 136, 620, 554, {"Category": [C("dOrigen", "OrigenCodigo")], "Y": [C("dOrigen", "OrigenLatitud")],
                                     "X": [C("dOrigen", "OrigenLongitud")], "Size": [M("Vuelos Demorados")],
                                     "Tooltips": [M("Vuelos"), M("% A Tiempo"), M("Demora Promedio de Demorados")]},
          title="Vuelos demorados por aeropuerto de origen")
    p.add("tableEx", 652, 136, 608, 272, {"Values": [
        C("dOrigen", "OrigenCodigo"), C("dOrigen", "OrigenCiudad"), C("dOrigen", "OrigenEstadoCod"), M("Vuelos"),
        M("% A Tiempo"), M("% Cancelados"), M("Taxi Salida Promedio")]},
          title="Aeropuertos de origen (ordenar por columna)", sort=(M("Vuelos"), "Descending"))
    p.add("tableEx", 652, 418, 608, 272, {"Values": [
        C("fVuelos", "Ruta"), M("Vuelos"), M("% A Tiempo"), M("% Cancelados"), M("Demora Promedio de Demorados")]},
          title="Rutas", sort=(M("Vuelos"), "Descending"))
    p.pie()
    P.append(p)

    # 4 CAUSAS ----------------------------------------------------------------
    p = Pagina("p4causas", "Causas de demora")
    p.encabezado("Por qué se demoran y cancelan los vuelos")
    kpis(p, 136, [(f"% Causa {c}", c) for c, _ in CAUSAS] + [("% Causa Controlable", "Controlable por aerolínea")])
    p.add("columnChart", 20, 240, 760, 220, {"Category": [C("dCalendario", "AnioMes")],
                                             "Y": [M(f"Min Demora {c}") for c, _ in CAUSAS]},
          title="Minutos de demora por causa y mes", sort=(C("dCalendario", "AnioMes"), "Ascending"))
    p.add("clusteredBarChart", 792, 240, 468, 220, {"Category": [C("dCausaCancelacion", "CausaCancelacion")],
                                                    "Y": [M("Vuelos Cancelados")]},
          title="Cancelaciones por causa", sort=(M("Vuelos Cancelados"), "Descending"))
    p.add("hundredPercentStackedBarChart", 20, 470, 1240, 220, {"Category": [C("dAerolinea", "Aerolinea")],
                                                                "Y": [M(f"Min Demora {c}") for c, _ in CAUSAS]},
          title="Mezcla de causas por aerolínea")
    p.pie()
    P.append(p)

    # 5 PATRONES --------------------------------------------------------------
    p = Pagina("p5patrones", "Patrones horarios")
    p.encabezado("Cuándo conviene volar")
    p.add("pivotTable", 20, 136, 1240, 250, {"Rows": [C("dCalendario", "DiaSemana")], "Columns": [C("dHora", "HoraTexto")],
                                             "Values": [M("% Demorados")]},
          title="% de vuelos demorados por día y hora programada de salida",
          objects={"values": [{"properties": {
              "backColor": {"solid": {"color": {"expr": {"Measure": {
                  "Expression": {"SourceRef": {"Entity": "fVuelos"}}, "Property": "Color % Demorados"}}}}},
              "fontColor": {"solid": {"color": lit("#FFFFFF")}}},
              "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "fVuelos.% Demorados"}}]})
    p.add("lineChart", 20, 396, 610, 294, {"Category": [C("dCalendario", "Mes")], "Series": [C("dCalendario", "Anio")],
                                           "Y": [M("% A Tiempo")]},
          title="Estacionalidad: % a tiempo por mes y año", sort=(C("dCalendario", "Mes"), "Ascending"))
    p.add("clusteredColumnChart", 642, 396, 300, 294, {"Category": [C("dHora", "FranjaHoraria")], "Y": [M("% A Tiempo")]},
          title="% a tiempo por franja", objects=barras_color(), sort=(C("dHora", "FranjaHoraria"), "Ascending"))
    p.add("clusteredColumnChart", 954, 396, 306, 294, {"Category": [C("dCalendario", "DiaSemana")], "Y": [M("% Cancelados")]},
          title="% cancelados por día", sort=(C("dCalendario", "DiaSemana"), "Ascending"))
    p.pie()
    P.append(p)

    # 6 DETALLE ---------------------------------------------------------------
    p = Pagina("p6detalle", "Detalle de vuelos")
    p.encabezado("Consulta vuelo por vuelo (filtrar antes)")
    p.add("tableEx", 20, 136, 1240, 554, {"Values": [
        C("dCalendario", "Fecha"), C("dAerolinea", "Aerolinea"), C("fVuelos", "NroVuelo"), C("fVuelos", "Ruta"),
        C("dHora", "HoraTexto"), C("fVuelos", "DemoraSalidaMin"), C("fVuelos", "DemoraLlegadaMin"),
        C("fVuelos", "Cancelado"), C("dCausaCancelacion", "CausaCancelacion"), C("fVuelos", "Desviado"),
        C("fVuelos", "DistanciaMillas")]}, title="Vuelos", sort=(C("fVuelos", "DemoraLlegadaMin"), "Descending"))
    p.pie()
    P.append(p)
    return P


TEMA = {
    "name": "ATLAS",
    "dataColors": PALETA,
    "foreground": AZUL, "foregroundNeutralSecondary": GRIS, "foregroundNeutralTertiary": "#8A97A6",
    "background": "#FFFFFF", "backgroundLight": FONDO, "backgroundNeutral": "#E1E6EC",
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
                          "values": [{"backColorSecondary": {"solid": {"color": FONDO}}}]}},
        "pivotTable": {"*": {"columnHeaders": [{"backColor": {"solid": {"color": AZUL}}, "fontColor": {"solid": {"color": "#FFFFFF"}}}],
                             "rowHeaders": [{"backColor": {"solid": {"color": AZUL}}, "fontColor": {"solid": {"color": "#FFFFFF"}}}]}},
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
    w(rr / "ATLAS_Tema.json", json.dumps(TEMA, indent=2, ensure_ascii=False))
    w(BASE / "ATLAS_Tema.json", json.dumps(TEMA, indent=2, ensure_ascii=False))
    w(d / "version.json", json.dumps({"$schema": f"{SCH}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2))
    w(d / "report.json", json.dumps({
        "$schema": f"{SCH}/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": BASE_THEME, "reportVersionAtImport": {"visual": "2.4.0", "report": "3.0.0", "page": "2.3.0"},
                          "type": "SharedResources"},
            "customTheme": {"name": "ATLAS_Tema.json", "reportVersionAtImport": {"visual": "2.4.0", "report": "3.0.0", "page": "2.3.0"},
                            "type": "RegisteredResources"}},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "ATLAS_Tema.json", "path": "ATLAS_Tema.json", "type": "CustomTheme"}]}],
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
