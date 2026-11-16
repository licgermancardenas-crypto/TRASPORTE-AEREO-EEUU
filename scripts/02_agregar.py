"""
ATLAS | BSI Transporte EEUU
Agrega fVuelos.parquet (21 M de vuelos) a tablas livianas para Power BI.
Procesa un grupo de filas (≈ un mes) por vez para usar poca memoria.

  fRutasMes   mes × aerolínea × origen × destino × causa de cancelación
  fPatrones   mes × aerolínea × día de semana × hora programada
  fDetalle    vuelo por vuelo, solo el último mes
  dMes, dDiaSemana

Uso: python -I 02_agregar.py
"""
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

DATA = Path(__file__).resolve().parent.parent / "data"
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
CAUSAS = ["DemoraAerolineaMin", "DemoraClimaMin", "DemoraNASMin", "DemoraSeguridadMin", "DemoraAvionPrevioMin"]
K_RUTAS = ["MesKey", "AerolineaCod", "OrigenCod", "DestinoCod", "CodigoCancelacion"]
K_PATRON = ["MesKey", "AerolineaCod", "DiaSemanaNum", "HoraProgramada"]  # sin aeropuerto: 90k filas vs 2,3 M


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    df["MesKey"] = (df["FechaKey"] // 100).astype("int32")
    fecha = pd.to_datetime(df["FechaKey"].astype(str), format="%Y%m%d")
    df["DiaSemanaNum"] = (fecha.dt.dayofweek + 1).astype("int8")
    df["Vuelos"] = 1
    lleg = df["DemoraLlegadaMin"]
    df["NDemoraLlegada"] = lleg.notna().astype("int8")
    df["SumaDemoraDemorados"] = lleg.where(df["LlegadaDemorada15"] == 1)
    df["NDemoraSalida"] = df["DemoraSalidaMin"].notna().astype("int8")
    df["NTaxiSalida"] = df["TaxiSalidaMin"].notna().astype("int8")
    return df


def rutas(df):
    g = df.groupby(K_RUTAS, observed=True).agg(
        Vuelos=("Vuelos", "sum"), Cancelados=("Cancelado", "sum"), Desviados=("Desviado", "sum"),
        LlegadasDemoradas=("LlegadaDemorada15", "sum"), SalidasDemoradas=("SalidaDemorada15", "sum"),
        SumaDemoraLlegada=("DemoraLlegadaMin", "sum"), NDemoraLlegada=("NDemoraLlegada", "sum"),
        SumaDemoraDemorados=("SumaDemoraDemorados", "sum"),
        SumaDemoraSalida=("DemoraSalidaMin", "sum"), NDemoraSalida=("NDemoraSalida", "sum"),
        SumaTaxiSalida=("TaxiSalidaMin", "sum"), NTaxiSalida=("NTaxiSalida", "sum"),
        Millas=("DistanciaMillas", "sum"), **{c: (c, "sum") for c in CAUSAS},
    ).reset_index()
    return g


def patrones(df):
    return df.groupby(K_PATRON, observed=True).agg(
        Vuelos=("Vuelos", "sum"), Cancelados=("Cancelado", "sum"), Desviados=("Desviado", "sum"),
        LlegadasDemoradas=("LlegadaDemorada15", "sum"),
        SumaDemoraDemorados=("SumaDemoraDemorados", "sum")).reset_index()


def compactar(df, claves):
    df = df.groupby(claves, observed=True).sum().reset_index()
    for c in df.columns:
        if c in claves:
            continue
        if c.startswith(("Vuelos", "Cancel", "Desv", "Llegadas", "Salidas", "N")):
            df[c] = df[c].astype("int32")
        else:
            df[c] = df[c].astype("float64")
    return df


def dmes(meskeys):
    m = pd.DataFrame({"MesKey": sorted(meskeys)})
    m["FechaMes"] = pd.to_datetime(m["MesKey"].astype(str) + "01", format="%Y%m%d")
    m["Anio"] = m["FechaMes"].dt.year.astype("int16")
    m["MesNum"] = m["FechaMes"].dt.month.astype("int8")
    m["Mes"] = [MESES[i - 1] for i in m["MesNum"]]
    m["AnioMes"] = m["FechaMes"].dt.strftime("%Y-%m")
    m["MesIndice"] = range(1, len(m) + 1)
    m["Trimestre"] = "T" + m["FechaMes"].dt.quarter.astype(str)
    m["Temporada"] = m["MesNum"].map(lambda x: "Invierno" if x in (12, 1, 2) else "Primavera" if x in (3, 4, 5)
                                     else "Verano" if x in (6, 7, 8) else "Otoño")
    return m


def main():
    pf = pq.ParquetFile(DATA / "fVuelos.parquet")
    R, P, meses = [], [], set()
    ultimo = None
    for i in range(pf.num_row_groups):
        df = preparar(pf.read_row_group(i).to_pandas())
        R.append(rutas(df))
        P.append(patrones(df))
        meses.update(df["MesKey"].unique())
        mx = df["MesKey"].max()
        if ultimo is None or mx > ultimo[0]:
            ultimo = (mx, df[df["MesKey"] == mx].copy())
        elif mx == ultimo[0]:
            ultimo = (mx, pd.concat([ultimo[1], df[df["MesKey"] == mx]]))
        print(f"  grupo {i + 1}/{pf.num_row_groups}: {len(df):,} vuelos", flush=True)
        del df

    fr = compactar(pd.concat(R), K_RUTAS)
    fp = compactar(pd.concat(P), K_PATRON)
    fd = ultimo[1][["FechaKey", "MesKey", "AerolineaCod", "NroVuelo", "OrigenCod", "DestinoCod", "Ruta",
                    "HoraProgramada", "DemoraSalidaMin", "DemoraLlegadaMin", "Cancelado", "CodigoCancelacion",
                    "Desviado", "DistanciaMillas"]].copy()
    fd["Fecha"] = pd.to_datetime(fd["FechaKey"].astype(str), format="%Y%m%d")
    fd = fd.drop(columns="FechaKey")

    fr.to_parquet(DATA / "fRutasMes.parquet", index=False, compression="zstd")
    fp.to_parquet(DATA / "fPatrones.parquet", index=False, compression="zstd")
    fd.to_parquet(DATA / "fDetalle.parquet", index=False, compression="zstd")
    dmes(meses).to_parquet(DATA / "dMes.parquet", index=False)
    pd.DataFrame({"DiaSemanaNum": range(1, 8), "DiaSemana": DIAS}).astype({"DiaSemanaNum": "int8"}) \
        .to_parquet(DATA / "dDiaSemana.parquet", index=False)

    print(f"\nfRutasMes {len(fr):,} filas | fPatrones {len(fp):,} | fDetalle {len(fd):,} (mes {ultimo[0]})")
    print(f"control: vuelos {fr['Vuelos'].sum():,} = {fp['Vuelos'].sum():,} | "
          f"% a tiempo {1 - fr.LlegadasDemoradas.sum() / (fr.Vuelos.sum() - fr.Cancelados.sum() - fr.Desviados.sum()):.2%}")
    for p in sorted(DATA.glob("*.parquet")):
        print(f"  {p.name}: {p.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
