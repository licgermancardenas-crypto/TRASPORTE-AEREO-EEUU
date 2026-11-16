# Mejoras de UI/UX: ATLAS | BSI Transporte EEUU

Este documento acompaña la revisión de UI/UX del 16/11/2026. La primera parte lista lo que ya quedó aplicado en los archivos del proyecto (PBIR + TMDL). La segunda explica, paso a paso, lo que falta hacer a mano en Power BI Desktop.

> **Importante:** `scripts/03_generar_pbip.py` vuelve a generar la carpeta `pbip/` desde cero y **pisa estos cambios**. No lo corras sin antes pasar estos cambios al script, o hacé un commit para poder recuperarlos.

---

## 1. Lo que ya está aplicado

| Cambio | Dónde | Estado |
|---|---|---|
| Tema nuevo `ATLAS_Theme.json` (lienzo `#F3F4F6`, tarjetas blancas con borde redondeado y sombra, semáforo `#10B981` / `#F59E0B` / `#EF4444`, Segoe UI) | raíz del proyecto + `StaticResources/RegisteredResources/`, registrado en `report.json` | ✅ |
| Panel de filtros nativo oculto (`outspacePane.visible = false`) | `report.json` | ✅ (se oculta para quien lee el reporte; en Desktop el autor lo sigue viendo) |
| Sombra sutil y borde gris claro con radio 10 px en las 59 tarjetas blancas | `visual.json` de cada visual | ✅ |
| Página 1: subtítulo de la banda reemplazado por el **título dinámico** | `p1resumen_03_titulo` | ✅ |
| Página 1: barra "% a tiempo por aerolínea" con semáforo 80 / 75 | `p1resumen_17_clusteredBarChart` → medida `Color Puntualidad` | ✅ |
| Página 2: **barras de datos** en "Vuelos" y "% a tiempo" | `p2aerolineas_10_tableEx` | ✅ |
| Página 5: mapa de calor con **escala divergente azul → claro → naranja** (apta para daltónicos) y texto que cambia de color para seguir siendo legible | medidas `Color % Demorados` y `Color Texto % Demorados` | ✅ |
| Página 6: fondo condicional en "Demora llegada (min)" (rojo claro si es > 60, verde claro si es ≤ 0) | `p6detalle_10_tableEx` → medida `Color Demora Llegada` | ✅ |
| Transiciones de página "Deslizar" | — | ❌ Power BI no tiene transiciones animadas entre páginas, ni en Desktop ni en el Servicio. No existe ninguna propiedad PBIR para activarlas. Ver la alternativa en la sección 2.5. |

El tema anterior (`ATLAS_Tema.json`) sigue en la raíz como referencia, pero el reporte ya no lo usa.

---

## 2. Pasos manuales en Power BI Desktop

Abrí `pbip/BSI_Transporte_EEUU.pbip`. Después de cada cambio, guardá con **Ctrl+S**.

### 2.1 Página 1 (Resumen): color de las burbujas del mapa según la puntualidad

El tamaño de las burbujas ya depende de **Vuelos**. Para colorearlas con el semáforo:

1. Seleccioná el mapa "Aeropuertos de origen (tamaño = vuelos)".
2. Panel **Visualizaciones** → **Formato** (ícono del pincel) → **Capas** → **Capa de burbujas** → **Color de relleno**.
3. Hacé clic en el botón **fx** que aparece junto al color.
4. En **Estilo de formato** elegí **Valor de campo**.
5. En **¿En qué campo debemos basarnos?** elegí `Medidas` → `Color Puntualidad`.
6. Aceptá.
7. Recomendado: cambiá el título a **"Aeropuertos de origen (tamaño = vuelos, color = % a tiempo)"**, así el lector entiende la codificación.

Repetí los mismos pasos en el mapa de la **Página 3** (`Vuelos demorados por aeropuerto de origen`) para que los dos mapas usen el mismo criterio.

> Si **Valor de campo** no aparece para ese mapa, usá **Escala de colores** sobre la medida `% A Tiempo`: mínimo `#EF4444`, centro `#F59E0B` (valor 0,775) y máximo `#10B981`.

Opcional: para que el mapa muestre todo el país al abrir, en **Formato → Configuración de la vista** desactivá **Vista automática** y fijá un zoom de 3 centrado en lat 39 / lon −97.

### 2.2 Página 2 (Comparativo): ajuste fino de las barras de datos

Las barras ya están aplicadas. Si querés modificarlas:

1. Seleccioná la tabla → **Formato** → **Elementos de celda**.
2. En **Configuración de la serie** elegí la columna (`Vuelos` o `% a tiempo`).
3. **Barras de datos** → **fx**: ahí se cambian los colores, la dirección y "Mostrar solo la barra".

Sugerencia: en "% a tiempo", poné **Mínimo = Número 0,70** y **Máximo = Número 0,90**. Con la escala por defecto (de 0 a 100 %), todas las barras se ven casi iguales porque los valores van de 72 % a 86 %.

El semáforo de la barra "% a tiempo por aerolínea" ya está aplicado (está en la Página 1). Si querés repetirlo en otro gráfico de barras: **Formato → Barras → Color → fx → Valor de campo → `Color Puntualidad`**.

### 2.3 Página 4 (Por qué se demoran): íconos en las 6 tarjetas KPI

**Opción A: rápida, con las tarjetas actuales.** Agregá un emoji al principio del título de cada tarjeta (**Formato → General → Título → Texto**):

| Tarjeta | Título sugerido |
|---|---|
| Operación aerolínea | `🛠️ Operación aerolínea` |
| Clima | `⛈️ Clima` |
| Sistema NAS | `🗼 Sistema NAS` |
| Seguridad | `🛡️ Seguridad` |
| Avión previo | `🔁 Avión previo` |
| Controlable por aerolínea | `✅ Controlable por aerolínea` |

**Opción B: más prolija, con la Tarjeta (nueva).**

1. Descargá íconos SVG o PNG (por ejemplo, de *Fluent UI System Icons* de Microsoft, licencia MIT) y guardalos en una carpeta `iconos/` del proyecto o subilos a una URL pública estable.
2. Insertá una **Tarjeta (nueva)** en el lugar de cada tarjeta actual y poné la misma medida (`% Causa Aerolínea`, `% Causa Clima`, etc.).
3. En **Formato → Imágenes**, activá la opción, elegí **Tipo de imagen: URL de imagen** (o **Imagen** para un archivo local), pegá el ícono y elegí **Posición: Izquierda**.
4. Copiá el formato de la tarjeta vieja con **Copiar formato** (la brocha) y borrá la tarjeta vieja.

### 2.4 Página 5 (Cuándo conviene volar): escala de color del mapa de calor

Ya está aplicada con medidas, en 6 tramos:

| % demorados | Color | Lectura |
|---|---|---|
| < 12 % | `#2166AC` azul oscuro | muy buena hora para volar |
| 12–16 % | `#67A9CF` azul | buena |
| 16–20 % | `#D1E5F0` celeste | normal |
| 20–24 % | `#FDDBC7` durazno | regular |
| 24–28 % | `#F4A15D` naranja | mala |
| ≥ 28 % | `#D9600F` naranja oscuro | peor hora |

Es la paleta divergente *RdBu* sin el rojo: azul contra naranja, que se distinguen con los tres tipos comunes de daltonismo. Para cambiar los cortes, editá la medida `Color % Demorados`. Si en cambio preferís una escala continua: **Formato → Elementos de celda → Color de fondo → fx → Escala de colores**, con mínimo `#2166AC`, centro `#F7F7F7` y máximo `#D9600F`. En ese caso, quitá también el **Color de fuente** por medida.

### 2.5 Transiciones entre páginas (alternativa)

Power BI no anima los cambios de página. Lo más parecido para dar sensación de navegación moderna:

1. **Insertar → Botones → Navegador → Navegador de páginas**: crea una barra de pestañas con botones. Ubicala en la banda morada y aplicale los colores del tema.
2. En **Ver**, desactivá **Mostrar pestañas de página** al publicar, para que la navegación pase por esos botones.
3. Usá el estado **Al mantener el puntero** de los botones (fondo `#7A5FB5`) para dar respuesta visual al pasar el mouse.

### 2.6 Página 6 (Consulta vuelo por vuelo)

El formato condicional ya está aplicado. Para cambiar los colores, editá la medida `Color Demora Llegada`. Si preferís que el número se pinte en vez de la celda: **Elementos de celda → Demora llegada (min) → Color de fuente → fx → Valor de campo → `Color Demora Llegada`**, y desactivá **Color de fondo**. En ese caso, usá los colores fuertes `#EF4444` y `#10B981` en la medida.

---

## 3. Medidas DAX

Todas están en la tabla `Medidas`, carpeta **9 Formato**.

### Título dinámico

```dax
Titulo Dinamico =
VAR anio =
    IF (
        HASONEVALUE ( dMes[Anio] ),
        " " & VALUES ( dMes[Anio] ),
        IF ( ISFILTERED ( dMes[Anio] ),
             " " & CONCATENATEX ( VALUES ( dMes[Anio] ), dMes[Anio], ", ", dMes[Anio] ),
             "" )
    )
VAR mes =
    IF (
        HASONEVALUE ( dMes[Mes] ),
        " " & VALUES ( dMes[Mes] ),
        IF ( ISFILTERED ( dMes[Mes] ), " (" & COUNTROWS ( VALUES ( dMes[Mes] ) ) & " meses)", "" )
    )
VAR filtro = TRIM ( anio & mes )
RETURN
    "Resumen de puntualidad" & IF ( filtro = "", " – todo el período", " – " & filtro )
```

Ejemplos: `Resumen de puntualidad – todo el período`, `Resumen de puntualidad – 2025 Julio`, `Resumen de puntualidad – 2024, 2025 (3 meses)`.

Para usarla como título de cualquier visual: **Formato → General → Título → Texto → fx → Valor de campo → `Titulo Dinamico`**.

### Semáforo de puntualidad

```dax
Color Puntualidad =
VAR v = [% A Tiempo]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( v ), BLANK (),
        v >= 0.80, "#10B981",   -- verde: bueno
        v >= 0.75, "#F59E0B",   -- ámbar: neutro
        "#EF4444"               -- rojo: malo
    )
```

`Color % A Tiempo` ahora devuelve `[Color Puntualidad]`, y `Color P % A Tiempo` usa los mismos cortes sobre `fPatrones`. Así todo el reporte comparte un solo criterio. **Ojo:** antes el corte del rojo era 72 %, ahora es 75 %. Por eso American Airlines, JetBlue y Frontier aparecen en rojo, y también las franjas Tarde, Noche y Noche tardía.

### Soporte del mapa de calor y del detalle

```dax
Color % Demorados =
VAR v = [P % Demorados]
RETURN
    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (),
        v < 0.12, "#2166AC", v < 0.16, "#67A9CF", v < 0.20, "#D1E5F0",
        v < 0.24, "#FDDBC7", v < 0.28, "#F4A15D", "#D9600F" )

Color Texto % Demorados =
VAR v = [P % Demorados]
RETURN
    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v < 0.16 || v >= 0.28, "#FFFFFF", "#1D1631" )

Color Demora Llegada =
VAR v = MAX ( fDetalle[DemoraLlegadaMin] )
RETURN
    SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v > 60, "#FDE2E2", v <= 0, "#D1FAE5", BLANK () )
```

En `Color Demora Llegada`, el verde cubre `≤ 0` y no solo `= 0`: una demora negativa significa que el vuelo llegó antes de hora, y también cuenta como "sin demora".
