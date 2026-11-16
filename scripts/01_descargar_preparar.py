"""
ATLAS | BSI Transporte EEUU
Descarga y prepara datos BTS On-Time Performance (36 meses) en modelo estrella Parquet.

Uso:  python -I 01_descargar_preparar.py [--desde 2023-09] [--hasta 2026-08]
Salida: ../data/*.parquet   Cache de ZIPs: ../raw/
"""
import argparse
import concurrent.futures as cf
import io
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "raw"
DATA = BASE / "data"
URL = "https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{y}_{m}.zip"
UA = {"User-Agent": "Mozilla/5.0 (data-download)"}

COLS = {
    "FlightDate": "str", "Reporting_Airline": "str", "Flight_Number_Reporting_Airline": "Int32",
    "Origin": "str", "OriginCityName": "str", "OriginState": "str", "OriginStateName": "str",
    "Dest": "str", "DestCityName": "str", "DestState": "str", "DestStateName": "str",
    "CRSDepTime": "Int32", "DepDelay": "float32", "ArrDelay": "float32", "ArrDel15": "float32",
    "DepDel15": "float32", "Cancelled": "float32", "CancellationCode": "str", "Diverted": "float32",
    "Distance": "float32", "AirTime": "float32", "TaxiOut": "float32", "TaxiIn": "float32",
    "CarrierDelay": "float32", "WeatherDelay": "float32", "NASDelay": "float32",
    "SecurityDelay": "float32", "LateAircraftDelay": "float32",
}

AEROLINEAS = {
    "AA": "American Airlines", "AS": "Alaska Airlines", "B6": "JetBlue Airways", "DL": "Delta Air Lines",
    "F9": "Frontier Airlines", "G4": "Allegiant Air", "HA": "Hawaiian Airlines", "MQ": "Envoy Air",
    "NK": "Spirit Air Lines", "OH": "PSA Airlines", "OO": "SkyWest Airlines", "UA": "United Air Lines",
    "WN": "Southwest Airlines", "YX": "Republic Airline", "9E": "Endeavor Air", "YV": "Mesa Airlines",
    "QX": "Horizon Air", "ZW": "Air Wisconsin", "PT": "Piedmont Airlines", "C5": "CommuteAir",
    "G7": "GoJet Airlines", "EV": "ExpressJet", "VX": "Virgin America", "MX": "Breeze Airways",
    "XP": "Avelo Airlines", "SY": "Sun Country Airlines",
}
TIPO = {  # red troncal vs regional / low cost
    "AA": "Troncal", "DL": "Troncal", "UA": "Troncal", "WN": "Troncal", "AS": "Troncal", "B6": "Troncal",
    "HA": "Troncal", "F9": "Low cost", "NK": "Low cost", "G4": "Low cost", "SY": "Low cost",
    "MX": "Low cost", "XP": "Low cost",
}
CAUSAS_CANC = pd.DataFrame({
    "CodigoCancelacion": ["A", "B", "C", "D", "N"],
    "CausaCancelacion": ["Aerolínea", "Clima", "Sistema Nacional (NAS)", "Seguridad", "No cancelado"],
})
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def meses(desde: str, hasta: str):
    p = pd.period_range(desde, hasta, freq="M")
    return [(x.year, x.month) for x in p]


def descargar(y: int, m: int) -> Path:
    dst = RAW / f"ontime_{y}_{m:02d}.zip"
    if dst.exists() and dst.stat().st_size > 1_000_000:
        return dst
    for intento in range(4):
        try:
            req = urllib.request.Request(URL.format(y=y, m=m), headers=UA)
            with urllib.request.urlopen(req, timeout=300) as r:
                data = r.read()
            zipfile.ZipFile(io.BytesIO(data)).testzip()
            tmp = dst.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(dst)
            print(f"  descargado {y}-{m:02d} ({len(data)/1e6:.0f} MB)", flush=True)
            return dst
        except Exception as e:  # noqa: BLE001
            print(f"  reintento {y}-{m:02d}: {e}", flush=True)
            time.sleep(5 * (intento + 1))
    raise RuntimeError(f"No se pudo descargar {y}-{m:02d}")


def leer(zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as z:
        csv = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(csv) as f:
            df = pd.read_csv(f, usecols=list(COLS), dtype=COLS, low_memory=False)
    return df


def a_hecho(df: pd.DataFrame) -> pd.DataFrame:
    fecha = pd.to_datetime(df["FlightDate"])
    out = pd.DataFrame({
        "FechaKey": (fecha.dt.year * 10000 + fecha.dt.month * 100 + fecha.dt.day).astype("int32"),
        "AerolineaCod": df["Reporting_Airline"],
        "NroVuelo": df["Flight_Number_Reporting_Airline"],  # Int32 nullable: algunos meses traen vacíos
        "OrigenCod": df["Origin"],
        "DestinoCod": df["Dest"],
        "Ruta": df["Origin"] + "-" + df["Dest"],
        "HoraProgramada": (df["CRSDepTime"].fillna(0) // 100).clip(0, 23).astype("int8"),
        "DemoraSalidaMin": df["DepDelay"],
        "DemoraLlegadaMin": df["ArrDelay"],
        "SalidaDemorada15": df["DepDel15"].fillna(0).astype("int8"),
        "LlegadaDemorada15": df["ArrDel15"].fillna(0).astype("int8"),
        "Cancelado": df["Cancelled"].fillna(0).astype("int8"),
        "Desviado": df["Diverted"].fillna(0).astype("int8"),
        "CodigoCancelacion": df["CancellationCode"].fillna("N"),
        "DistanciaMillas": df["Distance"],
        "TiempoAireMin": df["AirTime"],
        "TaxiSalidaMin": df["TaxiOut"],
        "TaxiLlegadaMin": df["TaxiIn"],
        "DemoraAerolineaMin": df["CarrierDelay"],
        "DemoraClimaMin": df["WeatherDelay"],
        "DemoraNASMin": df["NASDelay"],
        "DemoraSeguridadMin": df["SecurityDelay"],
        "DemoraAvionPrevioMin": df["LateAircraftDelay"],
    })
    return out


def aeropuertos_de(df: pd.DataFrame) -> pd.DataFrame:
    o = df[["Origin", "OriginCityName", "OriginState", "OriginStateName"]]
    o.columns = ["Codigo", "Ciudad", "EstadoCod", "Estado"]
    d = df[["Dest", "DestCityName", "DestState", "DestStateName"]]
    d.columns = o.columns
    return pd.concat([o, d]).drop_duplicates("Codigo")


def coords() -> pd.DataFrame:
    url = "https://davidmegginson.github.io/ourairports-data/airports.csv"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r:
            a = pd.read_csv(io.BytesIO(r.read()), usecols=["iata_code", "name", "latitude_deg", "longitude_deg", "type"])
        a = a.dropna(subset=["iata_code"])
        rank = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}
        a["r"] = a["type"].map(rank).fillna(9)
        a = a.sort_values("r").drop_duplicates("iata_code")
        return a.rename(columns={"iata_code": "Codigo", "name": "NombreAeropuerto",
                                 "latitude_deg": "Latitud", "longitude_deg": "Longitud"})[
            ["Codigo", "NombreAeropuerto", "Latitud", "Longitud"]]
    except Exception as e:  # noqa: BLE001
        print(f"  aviso: sin coordenadas ({e})")
        return pd.DataFrame(columns=["Codigo", "NombreAeropuerto", "Latitud", "Longitud"])


COORD_MANUAL = {  # aeropuertos que OurAirports no trae con código IATA
    "PBI": ("Palm Beach International Airport", 26.6832, -80.0956),
}


def completar_coords(ap_df: pd.DataFrame) -> pd.DataFrame:
    for cod, (nom, lat, lon) in COORD_MANUAL.items():
        m = (ap_df["Codigo"] == cod) & ap_df["Latitud"].isna()
        ap_df.loc[m, ["NombreAeropuerto", "Latitud", "Longitud"]] = [nom, lat, lon]
    return ap_df


def calendario(desde: str, hasta: str) -> pd.DataFrame:
    f = pd.date_range(pd.Period(desde).start_time, pd.Period(hasta).end_time.normalize(), freq="D")
    c = pd.DataFrame({"Fecha": f})
    c["FechaKey"] = (f.year * 10000 + f.month * 100 + f.day).astype("int32")
    c["Anio"] = f.year.astype("int16")
    c["MesNum"] = f.month.astype("int8")
    c["Mes"] = [MESES[m - 1] for m in f.month]
    c["MesCorto"] = c["Mes"].str[:3]
    c["AnioMes"] = f.strftime("%Y-%m")
    c["AnioMesOrden"] = (f.year * 100 + f.month).astype("int32")
    c["Trimestre"] = "T" + f.quarter.astype(str)
    c["DiaSemanaNum"] = (f.dayofweek + 1).astype("int8")
    c["DiaSemana"] = [DIAS[d] for d in f.dayofweek]
    c["EsFinDeSemana"] = f.dayofweek >= 5
    c["Temporada"] = pd.Series(f.month).map(lambda m: "Invierno" if m in (12, 1, 2) else "Primavera" if m in (3, 4, 5)
                                             else "Verano" if m in (6, 7, 8) else "Otoño").values
    return c


def horas() -> pd.DataFrame:
    h = pd.DataFrame({"HoraProgramada": range(24)})
    h["HoraTexto"] = h["HoraProgramada"].map(lambda x: f"{x:02d}:00")
    h["FranjaHoraria"] = pd.cut(h["HoraProgramada"], [-1, 5, 11, 17, 21, 23],
                                labels=["Madrugada (0-5)", "Mañana (6-11)", "Tarde (12-17)",
                                        "Noche (18-21)", "Noche tardía (22-23)"]).astype(str)
    orden = ["Madrugada (0-5)", "Mañana (6-11)", "Tarde (12-17)", "Noche (18-21)", "Noche tardía (22-23)"]
    h["FranjaOrden"] = h["FranjaHoraria"].map(orden.index).astype("int8")
    return h.astype({"HoraProgramada": "int8"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2023-09")
    ap.add_argument("--hasta", default="2026-08")
    ap.add_argument("--hilos", type=int, default=4)
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    lista = meses(a.desde, a.hasta)
    print(f"Descargando {len(lista)} meses...", flush=True)
    with cf.ThreadPoolExecutor(a.hilos) as ex:
        zips = list(ex.map(lambda ym: descargar(*ym), lista))

    print("Procesando...", flush=True)
    writer = None
    aerops, aerolineas, total = [], set(), 0
    for z in zips:
        df = leer(z)
        aerops.append(aeropuertos_de(df))
        aerolineas.update(df["Reporting_Airline"].dropna().unique())
        t = pa.Table.from_pandas(a_hecho(df), preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(DATA / "fVuelos.parquet", t.schema, compression="zstd")
        writer.write_table(t.cast(writer.schema))
        total += len(df)
        print(f"  {z.name}: {len(df):,} vuelos", flush=True)
    writer.close()

    ap_df = pd.concat(aerops).drop_duplicates("Codigo").merge(coords(), on="Codigo", how="left")
    ap_df = completar_coords(ap_df)
    ap_df["Ciudad"] = ap_df["Ciudad"].str.split(",").str[0]
    ap_df.sort_values("Codigo").to_parquet(DATA / "dAeropuerto.parquet", index=False)

    al = pd.DataFrame({"AerolineaCod": sorted(aerolineas)})
    al["Aerolinea"] = al["AerolineaCod"].map(AEROLINEAS).fillna(al["AerolineaCod"])
    al["TipoAerolinea"] = al["AerolineaCod"].map(TIPO).fillna("Regional")
    al.to_parquet(DATA / "dAerolinea.parquet", index=False)
    faltan = sorted(set(aerolineas) - set(AEROLINEAS))
    if faltan:
        print(f"  aviso: aerolíneas sin nombre: {faltan}")

    calendario(a.desde, a.hasta).to_parquet(DATA / "dCalendario.parquet", index=False)
    horas().to_parquet(DATA / "dHora.parquet", index=False)
    CAUSAS_CANC.to_parquet(DATA / "dCausaCancelacion.parquet", index=False)

    sin_coord = ap_df["Latitud"].isna().sum()
    print(f"\nOK: {total:,} vuelos | {len(ap_df)} aeropuertos ({sin_coord} sin coordenadas) | {len(al)} aerolíneas")
    for p in sorted(DATA.glob("*.parquet")):
        print(f"  {p.name}: {p.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    sys.exit(main())
