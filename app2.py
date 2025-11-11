# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ---------------------- Configuración de página ----------------------
st.set_page_config(page_title="US Shootings Dashboard — 2015 - Emiliano Razo", layout="wide")

# ---------------------- Encabezado HTML (requisito HTML) ----------------------
st.markdown(
    """
    <div style="padding:14px;border-radius:12px;background:linear-gradient(90deg,#111,#1f2937);color:#fff;margin-bottom:10px;">
      <h2 style="margin:0;">US Shootings Dashboard — 2015</h2>
      <p style="margin:2px 0 0 0;font-size:14px;opacity:.85">
        Basado en los análisis de la Tarea 1. Interactúa con los controles para ver el efecto en múltiples visualizaciones.
      </p>
    </div>
    """,
    unsafe_allow_html=True
)

# ---------------------- Barra lateral: Carga de archivos ----------------------
st.sidebar.header("1) Carga de archivos (.csv)")
pk_file         = st.sidebar.file_uploader("PoliceKillingsUS4.csv", type=["csv"])
pop_file        = st.sidebar.file_uploader("population2015.csv", type=["csv"])
inc_file        = st.sidebar.file_uploader("MedianHouseholdIncome2015.csv", type=["csv"])
race_share_file = st.sidebar.file_uploader("ShareRaceByCity2.csv", type=["csv"])
races_file      = st.sidebar.file_uploader("Races.csv", type=["csv"])

# (Opcional) 2 archivos extra por si quieres usarlos para más visualizaciones
poverty_file = st.sidebar.file_uploader("PercentagePeopleBelowPovertyLevel.csv", type=["csv"])
hs_file      = st.sidebar.file_uploader("PercentOver25CompletedHighSchool.csv", type=["csv"])

@st.cache_data
def read_csv_robust(file):
    if file is None:
        return None
    try:
        return pd.read_csv(file, low_memory=False)
    except UnicodeDecodeError:
        file.seek(0)
        return pd.read_csv(file, low_memory=False, encoding="latin-1")

def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (df.columns
                    .str.strip()
                    .str.replace(r"\s+", "_", regex=True)
                    .str.replace(r"[^\w_]", "", regex=True)
                    .str.lower())
    return df

# Leer
pk   = read_csv_robust(pk_file)
pop  = read_csv_robust(pop_file)
inc  = read_csv_robust(inc_file)
race_share = read_csv_robust(race_share_file)
races = read_csv_robust(races_file)
poverty = read_csv_robust(poverty_file)
hs      = read_csv_robust(hs_file)

# Requisito mínimo para arrancar
if pk is None or pop is None:
    st.info("Sube al menos **PoliceKillingsUS4.csv** y **population2015.csv** para comenzar.")
    st.stop()

# Normalizar columnas
pk = norm_cols(pk)
pop = norm_cols(pop)
if inc is not None: inc = norm_cols(inc)
if race_share is not None: race_share = norm_cols(race_share)
if races is not None: races = norm_cols(races)
if poverty is not None: poverty = norm_cols(poverty)
if hs is not None: hs = norm_cols(hs)

# ---------------------- Columnas clave y limpieza ----------------------
# Fecha
date_col = None
for c in ["new_date", "date", "incident_date"]:
    if c in pk.columns:
        date_col = c; break
if date_col is None:
    st.error("No se encontró columna de fecha en PoliceKillingsUS4 (ej. 'new_date').")
    st.stop()
pk[date_col] = pd.to_datetime(pk[date_col], errors="coerce")

# Estado / ciudad
state_col = "state" if "state" in pk.columns else None
city_col  = "city"  if "city"  in pk.columns else None
if state_col is None:
    st.error("No se encontró columna de estado ('state') en PoliceKillingsUS4.")
    st.stop()

# Población 2015: detecta columnas posibles
pop_state_col = None
for c in ["state", "state_name", "geographic_area"]:
    if c in pop.columns:
        pop_state_col = c; break

pop_pop_col = None
for c in ["2015_population", "population_2015", "population", "pop_2015"]:
    if c in pop.columns:
        pop_pop_col = c; break

if pop_state_col is None or pop_pop_col is None:
    st.error("population2015.csv debe contener columnas de estado y población (ej. 'State' & '2015 population').")
    st.stop()

# Preparar población
pop[pop_pop_col] = pop[pop_pop_col].astype(str).str.replace(",", "", regex=False)
pop_clean = pop[[pop_state_col, pop_pop_col]].rename(columns={
    pop_state_col: "state_name",
    pop_pop_col: "population_2015"
})
pop_clean["state_name"] = pop_clean["state_name"].astype(str).str.upper().str.strip()
pop_clean["population_2015"] = pd.to_numeric(pop_clean["population_2015"], errors="coerce")

# Ingreso (si está)
inc_clean = None
if inc is not None:
    inc_state = None
    for c in ["geographic_area", "state", "state_name"]:
        if c in inc.columns: inc_state = c; break
    inc_income = None
    for c in ["median_income", "median_household_income_2015", "median_household_income"]:
        if c in inc.columns: inc_income = c; break
    if inc_state and inc_income:
        inc_clean = inc[[inc_state, inc_income]].rename(columns={
            inc_state: "state_name",
            inc_income: "median_income"
        })
        inc_clean["state_name"] = inc_clean["state_name"].astype(str).str.upper().str.strip()
        inc_clean["median_income"] = pd.to_numeric(inc_clean["median_income"], errors="coerce")

# % población negra por estado (si está)
share_clean = None
if race_share is not None and "geographic_area" in race_share.columns and "share_black" in race_share.columns:
    share_clean = (race_share.groupby("geographic_area")["share_black"]
                   .mean().reset_index()
                   .rename(columns={"geographic_area": "state_name"}))
    share_clean["state_name"] = share_clean["state_name"].astype(str).str.upper().str.strip()

# ---------------------- Filtros globales ----------------------
st.sidebar.header("2) Controles globales")
years = sorted([y for y in pk[date_col].dt.year.dropna().unique() if not pd.isna(y)])
default_year = years[0] if len(years) else 2015
year = st.sidebar.selectbox("Año", options=years, index=0)
top_n = st.sidebar.slider("Top N estados", min_value=5, max_value=20, value=10, step=1)
use_rates = st.sidebar.checkbox("Mostrar tasas por millón (usa población 2015) ✅", value=True)

pk_year = pk[pk[date_col].dt.year == year].copy()

# ---------------------- Utilidades ----------------------
def add_rates(df_counts, name_col="state", count_col="count"):
    """Une población 2015 y calcula tasa por millón. Devuelve siempre 'state_name' y filtra NaN."""
    tmp = df_counts.copy()
    if "state_name" not in tmp.columns:
        tmp["state_name"] = tmp[name_col].astype(str).str.upper().str.strip()
    out = tmp.merge(pop_clean, on="state_name", how="left")
    out["population_2015"] = pd.to_numeric(out["population_2015"], errors="coerce")
    out = out.dropna(subset=["population_2015"])
    out["rate_per_million"] = (out[count_col] / out["population_2015"]) * 1_000_000
    return out

# ---------------------- Layout con Tabs ----------------------
tab1, tab2, tab3 = st.tabs([
    "Estados con más ciudades",
    "Salud mental + Ingreso",
    "Armas / Toy weapon / Demografía"
])

# ====================== TAB 1 ======================
with tab1:
    st.subheader("Estados con más ciudades donde ocurrió un tiroteo policial")

    if city_col is None:
        cities_by_state = (pk_year.groupby(state_col).size().reset_index(name="num_cities"))
    else:
        cities_by_state = (pk_year.groupby(state_col)[city_col].nunique()
                           .reset_index(name="num_cities"))
    cities_by_state = cities_by_state.sort_values("num_cities", ascending=False)

    fig1 = px.bar(cities_by_state.head(top_n), x=state_col, y="num_cities",
                  title=f"Top {top_n} estados por número de ciudades con tiroteo ({year})")
    st.plotly_chart(fig1, use_container_width=True)

    st.caption("Conclusión breve: California suele liderar en ciudades con incidentes, lo que indica una dispersión geográfica amplia de eventos en el estado.")

# ====================== TAB 2 ======================
with tab2:
    st.subheader("Muertes con indicios de enfermedad mental vs ingreso")

    if "signs_of_mental_illness" not in pk_year.columns:
        st.error("No se encontró columna 'signs_of_mental_illness' en PoliceKillingsUS4.")
    else:
        pk_m = pk_year[pk_year["signs_of_mental_illness"] == True]

        deaths_by_state = (pk_m.groupby(state_col)
                              .size()
                              .reset_index(name="num_deaths")
                              .sort_values("num_deaths", ascending=False))

        # ----- Barra principal
        if use_rates:
            barra_df = add_rates(deaths_by_state.rename(columns={state_col: "state"}),
                                 name_col="state", count_col="num_deaths")
            y_col = "rate_per_million"; y_title = "Tasa por millón"
        else:
            barra_df = deaths_by_state.copy()
            barra_df["state_name"] = barra_df[state_col].astype(str).str.upper().str.strip()
            y_col = "num_deaths"; y_title = "Número de muertes"

        fig2 = px.bar(barra_df.head(top_n), x=state_col, y=y_col,
                      title=f"Estados con más muertes (indic. salud mental) — {y_title} ({year})")
        st.plotly_chart(fig2, use_container_width=True)

        # ----- Scatter ingreso vs y_col
        if inc_clean is not None:
            scatter_df = barra_df.copy()
            if "state_name" not in scatter_df.columns:
                scatter_df["state_name"] = scatter_df[state_col].astype(str).str.upper().str.strip()
            scatter_df = scatter_df.merge(inc_clean, on="state_name", how="left")

            if scatter_df["median_income"].notna().sum() == 0:
                st.info("No se pudo unir ingreso mediano; revisa columnas en MedianHouseholdIncome2015.csv.")
            else:
                fig2b = px.scatter(scatter_df, x="median_income", y=y_col,
                                   hover_name="state_name",
                                   title=f"Ingreso mediano vs {y_title} (salud mental) ({year})",
                                   labels={"median_income": "Ingreso mediano 2015 (USD)", y_col: y_title})
                st.plotly_chart(fig2b, use_container_width=True)
        else:
            st.info("Sube MedianHouseholdIncome2015.csv para ver la comparación con ingresos.")

# ====================== TAB 3 ======================
with tab3:
    colA, colB = st.columns(2)

    # A) Armas más comunes
    with colA:
        st.markdown("**Armas más comunes utilizadas por los atacantes**")
        if "armed" not in pk_year.columns:
            st.warning("No se encontró columna 'armed'.")
        else:
            armed_counts = (pk_year["armed"].astype(str).str.strip().str.lower()
                            .replace({"nan": "unknown", "": "unknown"})
                            .value_counts().reset_index())
            armed_counts.columns = ["weapon", "count"]
            fig3 = px.bar(armed_counts.head(top_n).sort_values("count"),
                          x="count", y="weapon", orientation="h",
                          title=f"Top {top_n} armas más comunes ({year})")
            st.plotly_chart(fig3, use_container_width=True)

    # B) Toy weapon por estado
    with colB:
        st.markdown("**Incidentes con 'toy weapon' por estado**")
        if "armed" in pk_year.columns:
            armed_norm = pk_year["armed"].astype(str).str.lower()
            pk_toy = pk_year[armed_norm.str.contains(r"\btoy\b", na=False)]
            toy_by_state = pk_toy.groupby(state_col).size().reset_index(name="num_incidents")

            if use_rates:
                toy_by_state_r = add_rates(toy_by_state.rename(columns={state_col: "state"}),
                                           name_col="state", count_col="num_incidents")
                y_col_t = "rate_per_million"; y_title_t = "Tasa por millón"
            else:
                toy_by_state_r = toy_by_state.copy()
                toy_by_state_r["state_name"] = toy_by_state_r[state_col].astype(str).str.upper().str.strip()
                y_col_t = "num_incidents"; y_title_t = "Número de incidentes"

            fig4 = px.bar(toy_by_state_r.sort_values(y_col_t, ascending=False).head(top_n),
                          x=state_col, y=y_col_t,
                          title=f"Tiroteos con 'toy weapon' — {y_title_t} ({year})")
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No se encontró columna 'armed' para analizar 'toy weapon'.")

    st.markdown("---")

    # C) Tasas por perfil demográfico (dos columnas)
    st.markdown("**Tasas por perfil demográfico**")
    demo_cols = st.columns(2)

    def rate_by_demo(df, gender_code, race_code, age_min, age_max, label):
        if not all(col in df.columns for col in ["gender", "race", "age", state_col]):
            return None
        mask = (
            (df["gender"].astype(str).str.upper() == gender_code) &
            (df["race"].astype(str).str.upper() == race_code) &
            (pd.to_numeric(df["age"], errors="coerce").between(age_min, age_max, inclusive="both"))
        )
        d = df.loc[mask, [state_col]].copy()
        if d.empty:
            return None
        out = d.groupby(state_col).size().reset_index(name="count")
        out = add_rates(out.rename(columns={state_col: "state"}), "state", "count")
        out["label"] = label
        return out

    with demo_cols[0]:
        st.caption("Hombre blanco 25–40 años — tasa por millón")
        r1 = rate_by_demo(pk_year, "M", "W", 25, 40, "White male 25–40")
        if r1 is not None:
            fig5 = px.bar(r1.sort_values("rate_per_million", ascending=False).head(top_n),
                          x="state_name", y="rate_per_million",
                          title=f"Top {top_n} estados (Hombre blanco 25–40) — {year}")
            st.plotly_chart(fig5, use_container_width=True)
        else:
            st.info("No hay datos suficientes para 'Hombre blanco 25–40'.")

    with demo_cols[1]:
        st.caption("Mujer negra 25–40 años — tasa por millón")
        r2 = rate_by_demo(pk_year, "F", "B", 25, 40, "Black female 25–40")
        if r2 is not None:
            fig6 = px.bar(r2.sort_values("rate_per_million", ascending=False).head(top_n),
                          x="state_name", y="rate_per_million",
                          title=f"Top {top_n} estados (Mujer negra 25–40) — {year}")
            st.plotly_chart(fig6, use_container_width=True)
        else:
            st.info("No hay datos suficientes para 'Mujer negra 25–40'.")

    # D) Dispersión % población negra vs muertes totales (si se sube ShareRaceByCity2.csv)
    if share_clean is not None:
        st.markdown("**% población negra vs número de muertes (dispersión)**")
        deaths_by_state_total = pk_year.groupby(state_col).size().reset_index(name="num_deaths")
        scatter_df = deaths_by_state_total.rename(columns={state_col: "state"}).copy()
        scatter_df["state_name"] = scatter_df["state"].astype(str).str.upper().str.strip()
        scatter_df = scatter_df.merge(share_clean, on="state_name", how="left")
        fig7 = px.scatter(scatter_df, x="share_black", y="num_deaths", hover_name="state_name",
                          labels={"share_black": "% población negra promedio (estatal)", "num_deaths": "Muertes (total)"},
                          title=f"% población negra vs muertes por estado ({year})")
        st.plotly_chart(fig7, use_container_width=True)
    else:
        st.info("Sube ShareRaceByCity2.csv para ver la dispersión por % de población negra.")

# ---------------------- Footer ----------------------
st.caption("© Tarea 2 · Streamlit · Visualización basada en datasets del curso (2015)")

