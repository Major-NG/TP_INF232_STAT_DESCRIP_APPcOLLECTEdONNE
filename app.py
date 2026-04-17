import streamlit as st
from supabase import create_client, Client
import pandas as pd
import numpy as np
import altair as alt
from uuid import uuid4

st.set_page_config(page_title="Observatoire Bien-être & Mobilité Étudiante", layout="wide")

# ---------- Connexion Supabase ----------
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)

supabase = init_supabase()

# ---------- Constantes ----------
PERIODS = ["Session normale", "Examens", "Vacances"]
MOODS = ["Épanoui", "Neutre", "Épuisé"]
SPORT_FREQ = ["Jamais", "1-2/sem", "3-4/sem", "Quotidien"]
PSY_SUPPORT = ["Non disponible", "Disponible", "Utilisé"]

TRANSPORT_MODES = ["Bus", "Taxi", "Marche", "Vélo", "Voiture", "Moto", "Autre"]
ISSUE_OPTIONS = ["Retards", "Surcharge", "Insécurité", "Coût élevé", "Manque de lignes", "Autre"]

# ---------- Helpers ----------
@st.cache_data(ttl=300)
def load_wellbeing():
    res = supabase.table("wellbeing").select("*").order("submitted_at", desc=False).execute()
    df = pd.DataFrame(res.data or [])
    if not df.empty:
        df["submitted_at"] = pd.to_datetime(df["submitted_at"], errors="coerce", utc=True)
        num_cols = ["stress_level", "sleep_hours", "free_time_hours"]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

@st.cache_data(ttl=300)
def load_mobility():
    res = supabase.table("mobility").select("*").order("submitted_at", desc=False).execute()
    df = pd.DataFrame(res.data or [])
    if not df.empty:
        df["submitted_at"] = pd.to_datetime(df["submitted_at"], errors="coerce", utc=True)
        num_cols = ["commute_minutes", "monthly_cost", "satisfaction"]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["issues"] = df.get("issues", "").fillna("").astype(str)

        def to_hour(x):
            try:
                return pd.to_datetime(x, format="%H:%M").hour
            except Exception:
                return np.nan

        if "arrival_time" in df.columns:
            df["arrival_hour"] = df["arrival_time"].apply(to_hour)
        if "departure_time" in df.columns:
            df["departure_hour"] = df["departure_time"].apply(to_hour)
    return df

def insert_row(table: str, rec: dict):
    try:
        supabase.table(table).insert(rec).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def unique_non_null(df: pd.DataFrame, col: str):
    if df is None or df.empty or col not in df.columns:
        return []
    return df[col].dropna().unique().tolist()

# ---------- UI ----------
st.title("Observatoire Bien-être & Mobilité Étudiante")
st.caption("Collecte anonyme. Objectif: comprendre le bien-être des étudiants et l’impact de la mobilité sur le quotidien.")

tab_form, tab_analytics = st.tabs(["Contribuer", "Analyse"])

with tab_form:
    st.subheader("Ajouter une contribution")
    st.write("Réponds sur le bien-être, la mobilité, ou fais le questionnaire complet.")

    contrib_type = st.radio("Type de contribution", ["Bien-être", "Mobilité", "Complet (les deux)"], horizontal=True, key="contrib_type")

    with st.form("combo_form", clear_on_submit=True):
        # Identifiants communs (sans données perso)
        c0, c1, c2 = st.columns(3)
        with c0:
            participant_code = st.text_input(
                "Code participant anonyme (optionnel)",
                placeholder="ex: ABC12 (garde-le pour lier tes réponses)",
                key="participant_code_input",
            )
        with c1:
            city = st.text_input("Ville*", placeholder="ex: Dakar", key="city_input")
        with c2:
            university = st.text_input("Université / Campus (optionnel)", placeholder="ex: UCAD", key="university_input")

        # --- BIEN-ÊTRE ---
        wb_vals = {}
        if contrib_type in ["Bien-être", "Complet (les deux)"]:
            st.markdown("### Bien-être")
            w1, w2, w3 = st.columns(3)
            with w1:
                period = st.selectbox("Période*", PERIODS, index=0, key="period_select")
                stress = st.slider("Niveau de stress (1-10)*", 1, 10, 5, key="stress_slider")
                mood = st.selectbox("Sentiment général*", MOODS, index=1, key="mood_select")
            with w2:
                sleep = st.number_input("Heures de sommeil par nuit*", min_value=0.0, max_value=24.0, value=7.0, step=0.5, key="sleep_input")
                free_time = st.number_input("Temps libre par semaine (heures)*", min_value=0.0, max_value=168.0, value=10.0, step=1.0, key="free_time_input")
                sport = st.selectbox("Pratique sportive*", SPORT_FREQ, index=1, key="sport_select")
            with w3:
                psy = st.selectbox("Soutien psychologique*", PSY_SUPPORT, index=1, key="psy_select")
                wb_comment = st.text_area("Commentaire (optionnel)", key="wb_comment")
            wb_vals = dict(
                period=period, stress_level=stress, sleep_hours=sleep, free_time_hours=free_time,
                mood=mood, sport_freq=sport, psych_support=psy, comment=wb_comment
            )

        # --- MOBILITÉ ---
        mob_vals = {}
        if contrib_type in ["Mobilité", "Complet (les deux)"]:
            st.markdown("### Mobilité")
            m1, m2, m3 = st.columns(3)
            with m1:
                mode = st.selectbox("Mode de transport principal*", TRANSPORT_MODES, index=0, key="mode_select")
                commute = st.number_input("Temps de trajet (minutes)*", min_value=0, max_value=300, value=30, step=5, key="commute_input")
                satisfaction = st.slider("Satisfaction transport (1-5)*", 1, 5, 3, key="satisfaction_slider")
            with m2:
                cost = st.number_input("Coût mensuel transport", min_value=0.0, value=0.0, step=100.0, key="cost_input")
                arrival = st.text_input("Heure d'arrivée sur campus (HH:MM)", placeholder="ex: 08:30", key="arrival_input")
                departure = st.text_input("Heure de départ du campus (HH:MM)", placeholder="ex: 18:00", key="departure_input")
            with m3:
                issues = st.multiselect("Problèmes rencontrés", ISSUE_OPTIONS, default=[], key="issues_multiselect")
                mob_comment = st.text_area("Commentaire (optionnel)", key="mob_comment")
            mob_vals = dict(
                transport_mode=mode, commute_minutes=int(commute), monthly_cost=float(cost),
                arrival_time=arrival.strip(), departure_time=departure.strip(),
                satisfaction=int(satisfaction), issues=";".join(issues), comment=mob_comment
            )

        consent = st.checkbox("J'accepte l'utilisation anonyme de mes données pour des analyses agrégées.", value=True, key="consent_checkbox")
        submitted = st.form_submit_button("Envoyer")

        if submitted:
            missing = []
            if not city:
                missing.append("ville")
            if contrib_type in ["Mobilité", "Complet (les deux)"]:
                if mob_vals.get("commute_minutes", 0) <= 0:
                    missing.append("trajet > 0")
            if not consent:
                missing.append("consentement")

            if missing:
                st.error(f"Champs à corriger: {', '.join(missing)}")
            else:
                final_code = participant_code.strip() if participant_code else ""
                if contrib_type == "Complet (les deux)" and not final_code:
                    final_code = str(uuid4())[:8]
                saved = []
                errs = []

                if contrib_type in ["Bien-être", "Complet (les deux)"]:
                    rec_wb = {
                        "participant_code": final_code or None,
                        "city": city.strip(),
                        "university": (university or "").strip(),
                        "period": wb_vals["period"],
                        "stress_level": wb_vals["stress_level"],
                        "sleep_hours": wb_vals["sleep_hours"],
                        "free_time_hours": wb_vals["free_time_hours"],
                        "mood": wb_vals["mood"],
                        "sport_freq": wb_vals["sport_freq"],
                        "psych_support": wb_vals["psych_support"],
                        "comment": (wb_vals.get("comment") or "").strip(),
                    }
                    ok, err = insert_row("wellbeing", rec_wb)
                    saved.append(ok); errs.append(err)

                if contrib_type in ["Mobilité", "Complet (les deux)"]:
                    rec_mob = {
                        "participant_code": (final_code or participant_code or "").strip() or None,
                        "city": city.strip(),
                        "university": (university or "").strip(),
                        "transport_mode": mob_vals["transport_mode"],
                        "commute_minutes": mob_vals["commute_minutes"],
                        "monthly_cost": mob_vals["monthly_cost"],
                        "arrival_time": mob_vals["arrival_time"] or None,
                        "departure_time": mob_vals["departure_time"] or None,
                        "satisfaction": mob_vals["satisfaction"],
                        "issues": mob_vals["issues"] or None,
                        "comment": (mob_vals.get("comment") or "").strip(),
                    }
                    ok, err = insert_row("mobility", rec_mob)
                    saved.append(ok); errs.append(err)

                if all(saved):
                    msg = "Merci. Contribution enregistrée."
                    if final_code and not participant_code:
                        msg += f" Ton code participant (à garder pour lier tes réponses) : {final_code}"
                    st.success(msg)
                    st.rerun()
                else:
                    st.error("Erreur lors de l'enregistrement: " + "; ".join([e for e in errs if e]))

with tab_analytics:
    st.subheader("Analyse descriptive")
    wb = load_wellbeing()
    mob = load_mobility()

    all_cities = sorted(set(unique_non_null(wb, "city") + unique_non_null(mob, "city")))
    pick_city = st.selectbox("Ville", ["Toutes"] + all_cities, index=0, key="filter_city")

    all_unis = sorted(set(unique_non_null(wb, "university") + unique_non_null(mob, "university")))
    pick_uni = st.selectbox("Université/Campus", ["Toutes"] + all_unis, index=0, key="filter_uni")

    pick_period = st.selectbox("Période (pour bien-être)", ["Toutes"] + PERIODS, index=0, key="filter_period")

    def apply_filters(df, kind="wb"):
        if df is None or df.empty:
            return df
        dff = df.copy()
        if pick_city != "Toutes":
            dff = dff[dff["city"] == pick_city]
        if pick_uni != "Toutes" and "university" in dff.columns:
            dff = dff[dff["university"] == pick_uni]
        if kind == "wb" and pick_period != "Toutes":
            dff = dff[dff["period"] == pick_period]
        return dff

    wb_f = apply_filters(wb, "wb")
    mob_f = apply_filters(mob, "mob")

    tab_wb, tab_mob, tab_links = st.tabs(["Bien-être", "Mobilité", "Liens entre les deux"])

    with tab_wb:
        if wb_f is None or wb_f.empty:
            st.info("Pas encore de données bien-être pour ces filtres.")
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric("Contributions", f"{len(wb_f):,}".replace(",", " "))
            k2.metric("Stress médian", int(np.nanmedian(wb_f["stress_level"])) if "stress_level" in wb_f else "-")
            k3.metric("Sommeil moyen (h)", f"{np.nanmean(wb_f['sleep_hours']):.1f}" if "sleep_hours" in wb_f else "-")

            st.write("Distribution du stress (1-10)")
            chart = alt.Chart(wb_f).mark_bar().encode(
                x=alt.X("stress_level:Q", bin=alt.Bin(maxbins=10), title="Stress"),
                y=alt.Y("count():Q", title="Contributions"),
                tooltip=[alt.Tooltip("count():Q", title="N")]
            ).properties(height=250)
            st.altair_chart(chart, use_container_width=True)

            if "sleep_hours" in wb_f and "stress_level" in wb_f and wb_f["sleep_hours"].notna().sum() > 2:
                corr = np.corrcoef(wb_f["sleep_hours"], wb_f["stress_level"])[0, 1]
                st.write(f"Corrélation sommeil ↔ stress (Pearson) : {corr:.2f} (indicatif)")
                scat = alt.Chart(wb_f).mark_circle(size=60, opacity=0.6).encode(
                    x=alt.X("sleep_hours:Q", title="Sommeil (h)"),
                    y=alt.Y("stress_level:Q", title="Stress (1-10)"),
                    color=alt.Color("period:N", title="Période"),
                    tooltip=["sleep_hours", "stress_level", "period", "city", "university"]
                ).properties(height=300)
                st.altair_chart(scat, use_container_width=True)

            if "sport_freq" in wb_f and "stress_level" in wb_f:
                grp = (wb_f.groupby("sport_freq", as_index=False)["stress_level"]
                       .median().rename(columns={"stress_level": "stress_median"}))
                grp["sport_freq"] = pd.Categorical(grp["sport_freq"], categories=SPORT_FREQ, ordered=True)
                grp = grp.sort_values("sport_freq")
                st.write("Effet de la pratique sportive (stress médian)")
                bar = alt.Chart(grp).mark_bar().encode(
                    x=alt.X("sport_freq:N", title="Fréquence sport"),
                    y=alt.Y("stress_median:Q", title="Stress médian"),
                    tooltip=["sport_freq", "stress_median"]
                ).properties(height=250)
                st.altair_chart(bar, use_container_width=True)

    with tab_mob:
        if mob_f is None or mob_f.empty:
            st.info("Pas encore de données mobilité pour ces filtres.")
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric("Contributions", f"{len(mob_f):,}".replace(",", " "))
            k2.metric("Trajet moyen (min)", f"{np.nanmean(mob_f['commute_minutes']):.0f}" if "commute_minutes" in mob_f else "-")
            if "transport_mode" in mob_f and not mob_f["transport_mode"].empty:
                top_mode = mob_f["transport_mode"].mode().iloc[0]
            else:
                top_mode = "-"
            k3.metric("Mode le plus utilisé", top_mode)

            st.write("Répartition par mode de transport")
            mode_grp = mob_f.groupby("transport_mode", as_index=False).size().rename(columns={"size": "n"})
            bar = alt.Chart(mode_grp).mark_bar().encode(
                x=alt.X("transport_mode:N", title="Mode"),
                y=alt.Y("n:Q", title="Contributions"),
                tooltip=["transport_mode", "n"]
            ).properties(height=250)
            st.altair_chart(bar, use_container_width=True)

            st.write("Distribution du temps de trajet (min)")
            hist = alt.Chart(mob_f).mark_bar().encode(
                x=alt.X("commute_minutes:Q", bin=alt.Bin(maxbins=30), title="Minutes"),
                y=alt.Y("count():Q", title="Contributions")
            ).properties(height=250)
            st.altair_chart(hist, use_container_width=True)

            if "satisfaction" in mob_f and "commute_minutes" in mob_f:
                scat = alt.Chart(mob_f).mark_circle(size=60, opacity=0.6).encode(
                    x=alt.X("commute_minutes:Q", title="Trajet (min)"),
                    y=alt.Y("satisfaction:Q", title="Satisfaction (1-5)"),
                    color=alt.Color("transport_mode:N", title="Mode"),
                    tooltip=["commute_minutes", "satisfaction", "transport_mode", "city", "university"]
                ).properties(height=300)
                st.altair_chart(scat, use_container_width=True)

            if "issues" in mob_f and mob_f["issues"].str.len().sum() > 0:
                exploded = (mob_f.assign(issue_list=mob_f["issues"].str.split(";"))
                            .explode("issue_list"))
                issues_grp = exploded[exploded["issue_list"].notna()].groupby("issue_list", as_index=False).size()
                if not issues_grp.empty:
                    st.write("Problèmes signalés")
                    bar2 = alt.Chart(issues_grp).mark_bar().encode(
                        x=alt.X("issue_list:N", title="Problème"),
                        y=alt.Y("size:Q", title="Fréquence"),
                        tooltip=["issue_list", "size"]
                    ).properties(height=250)
                    st.altair_chart(bar2, use_container_width=True)

    with tab_links:
        if (wb is None or wb.empty) or (mob is None or mob.empty):
            st.info("Ajoute des données bien-être et mobilité pour voir les liens.")
        else:
            agg_level = st.radio("Niveau d’agrégation pour le lien", ["Ville", "Université"], horizontal=True, key="agg_level")

            if agg_level == "Ville":
                wb_agg = wb_f.groupby(["city"], as_index=False).agg(
                    avg_stress=("stress_level", "mean"),
                    avg_sleep=("sleep_hours", "mean"),
                    n_wb=("id", "count") if "id" in wb_f else ("stress_level", "count"),
                )
                mob_agg = mob_f.groupby(["city"], as_index=False).agg(
                    avg_commute=("commute_minutes", "mean"),
                    avg_cost=("monthly_cost", "mean"),
                    avg_satisfaction=("satisfaction", "mean"),
                    n_mob=("id", "count") if "id" in mob_f else ("commute_minutes", "count"),
                )
                joined = pd.merge(wb_agg, mob_agg, on="city", how="inner")
                label = "city"
            else:
                wb_agg = wb_f.groupby(["university"], as_index=False).agg(
                    avg_stress=("stress_level", "mean"),
                    avg_sleep=("sleep_hours", "mean"),
                    n_wb=("id", "count") if "id" in wb_f else ("stress_level", "count"),
                )
                mob_agg = mob_f.groupby(["university"], as_index=False).agg(
                    avg_commute=("commute_minutes", "mean"),
                    avg_cost=("monthly_cost", "mean"),
                    avg_satisfaction=("satisfaction", "mean"),
                    n_mob=("id", "count") if "id" in mob_f else ("commute_minutes", "count"),
                )
                joined = pd.merge(wb_agg, mob_agg, on="university", how="inner")
                label = "university"

            if joined.empty or joined["avg_commute"].notna().sum() < 2:
                st.info("Pas assez de points agrégés pour estimer un lien.")
            else:
                corr = np.corrcoef(joined["avg_commute"], joined["avg_stress"])[0, 1]
                st.write(f"Corrélation (agrégée) temps de trajet ↔ stress : {corr:.2f} (indicatif).")

                scat = alt.Chart(joined).mark_circle(size=120, opacity=0.7).encode(
                    x=alt.X("avg_commute:Q", title="Trajet moyen (min)"),
                    y=alt.Y("avg_stress:Q", title="Stress moyen (1-10)"),
                    size=alt.Size("n_wb:Q", title="N bien-être"),
                    color=alt.Color(f"{label}:N", title=("Ville" if label == "city" else "Université")),
                    tooltip=[label, "avg_commute", "avg_stress", "avg_sleep", "avg_satisfaction", "n_wb", "n_mob"]
                ).properties(height=320)
                st.altair_chart(scat, use_container_width=True)

            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "Télécharger (CSV) Bien-être filtré",
                    data=wb_f.to_csv(index=False).encode("utf-8"),
                    file_name="bien_etre_filtre.csv",
                    mime="text/csv",
                    key="dl_wb"
                )
            with c2:
                st.download_button(
                    "Télécharger (CSV) Mobilité filtrée",
                    data=mob_f.to_csv(index=False).encode("utf-8"),
                    file_name="mobilite_filtre.csv",
                    mime="text/csv",
                    key="dl_mob"
                )

st.caption("Vie privée: pas d'identifiants personnels. Le code participant est optionnel et anonyme.")
