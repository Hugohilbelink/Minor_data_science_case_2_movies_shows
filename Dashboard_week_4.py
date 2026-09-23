"""Case 2: Netflix en Amazon Prime vergelijken. Start: streamlit run Dashboard_week_4.py.

Opbouw zoals case 1: vraag, inladen, datacheck, afgeleide variabelen, EDA, conclusie.
API- en bibliotheekdocumentatie staan onderaan in de app en in README.md.
"""

from datetime import datetime, timezone
from pathlib import Path
import unicodedata

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# 1. Instellingen: vaste kleuren maken de platforms overal herkenbaar.
MAP = Path(__file__).resolve().parent
PLATFORMS = ["Netflix", "Amazon Prime"]
KLEUREN = {"Netflix": "#D81F36", "Amazon Prime": "#0086B3"}
SLEUTEL = ["titel_sleutel", "type", "release_year"]
BESTANDEN = {"Netflix": "netflix_titles.csv", "Amazon Prime": "amazon_prime_titles.csv"}

# Alleen inhoudelijk vergelijkbare labels samenvoegen. Dit is een eigen indeling.
GENRES = {
    "Drama": ["Drama", "Dramas", "TV Dramas"],
    "Komedie": ["Comedy", "Comedies", "TV Comedies", "Stand-Up Comedy"],
    "Actie & avontuur": ["Action", "Adventure", "Action & Adventure", "TV Action & Adventure"],
    "Documentaire": ["Documentary", "Documentaries", "Docuseries"],
    "Kinderen & familie": ["Kids", "Kids' TV", "Children & Family Movies"],
    "Romantiek": ["Romance", "Romantic Movies", "Romantic TV Shows"],
    "Horror": ["Horror", "Horror Movies", "TV Horror"],
    "Thriller & spanning": ["Suspense", "Thrillers", "TV Thrillers"],
    "Sciencefiction & fantasy": ["Science Fiction", "Fantasy", "Sci-Fi & Fantasy", "TV Sci-Fi & Fantasy"],
    "Anime": ["Anime", "Anime Series", "Anime Features"],
}
GENRE_MAP = {label: groep for groep, labels in GENRES.items() for label in labels}


def normaliseer(titel):
    """Behoud leestekens en accenten, negeer alleen hoofdletters en extra spaties."""
    return " ".join(unicodedata.normalize("NFKC", str(titel)).casefold().split())


def genre_groepen(tekst):
    # Het Amazon-label bevat zelf komma's: bescherm dat voordat we splitsen.
    labels = str(tekst).replace("Arts, Entertainment, and Culture", "Arts & Culture").split(",")
    return sorted({GENRE_MAP[label.strip()] for label in labels if label.strip() in GENRE_MAP})


@st.cache_data
def laad_data():
    """Lees de ongewijzigde CSV's, bewaar ruwe data en maak aparte analysekolommen."""
    ruwe_data, tabellen, controles = {}, [], []
    for platform, bestand in BESTANDEN.items():
        raw = pd.read_csv(MAP / bestand)
        ruwe_data[platform] = raw
        df = raw.drop_duplicates().copy()
        df["platform"] = platform
        df["titel_sleutel"] = df["title"].map(normaliseer)
        df["soort"] = df["type"].map({"Movie": "Film", "TV Show": "Serie"})
        df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce")
        ongeldig_jaar = ~df["release_year"].between(1888, datetime.now().year)
        df.loc[ongeldig_jaar, "release_year"] = float("nan")

        # Bij drie Netflix-rijen staat de speelduur per ongeluk in rating.
        herstel = df["duration"].isna() & df["rating"].str.fullmatch(r"\d+ min", na=False)
        df.loc[herstel, "duration"] = df.loc[herstel, "rating"]
        df.loc[herstel, "rating"] = pd.NA
        minuten = pd.to_numeric(df["duration"].str.extract(r"^(\d+) min$")[0], errors="coerce")
        seizoenen = pd.to_numeric(df["duration"].str.extract(r"^(\d+) Seasons?$")[0], errors="coerce")
        df["minuten"] = minuten.where(df["type"].eq("Movie") & minuten.gt(0))
        df["seizoenen"] = seizoenen.where(df["type"].eq("TV Show") & seizoenen.gt(0))
        df["genres"] = df["listed_in"].map(genre_groepen)
        controles.append({
            "Platform": platform, "Ruwe rijen": len(raw), "Analyse-rijen": len(df),
            "Exact dubbele rijen": int(raw.duplicated().sum()),
            "Dubbele show_id": int(raw["show_id"].duplicated().sum()),
            "Dubbele koppelsleutel": int(df.duplicated(SLEUTEL).sum()),
            "Ongeldige releasejaren": int(ongeldig_jaar.sum()),
            "Herstelde speelduur": int(herstel.sum()),
            "Niet-positieve speelduur": int(minuten.le(0).sum()),
            "Onbekende filmduur na opschonen": int((df["type"].eq("Movie") & df["minuten"].isna()).sum()),
            "Vroegste release": int(df["release_year"].min()),
            "Laatste release": int(df["release_year"].max()),
        })
        tabellen.append(df)
    return pd.concat(tabellen, ignore_index=True), ruwe_data, pd.DataFrame(controles)


def koppel_catalogi(data):
    """Outer join op titel + type + releasejaar; nooit op lokale show_id's."""
    links = data.loc[data.platform.eq("Netflix"), SLEUTEL + ["title"]].drop_duplicates(SLEUTEL)
    rechts = data.loc[data.platform.eq("Amazon Prime"), SLEUTEL + ["title"]].drop_duplicates(SLEUTEL)
    samen = links.merge(rechts, on=SLEUTEL, how="outer", suffixes=("_netflix", "_amazon"),
                        indicator=True, validate="one_to_one")
    samen["Titel"] = samen["title_netflix"].fillna(samen["title_amazon"])
    samen["Aanbod"] = samen["_merge"].map({
        "left_only": "Alleen in Netflix-dataset", "right_only": "Alleen in Amazon-dataset", "both": "In beide datasets"
    }).astype(str)
    return samen


def aantallen_per_categorie(data, kolom, categorieen=None):
    categorieen = categorieen if categorieen is not None else sorted(data[kolom].dropna().unique())
    index = pd.MultiIndex.from_product([PLATFORMS, categorieen], names=["platform", kolom])
    tabel = data.groupby(["platform", kolom]).size().reindex(index, fill_value=0).rename("Aantal").reset_index()
    noemer = data.groupby("platform").size()
    tabel["Percentage"] = 100 * tabel["Aantal"] / tabel.platform.map(noemer)
    return tabel


@st.cache_data(ttl=86400, show_spinner=False)
def haal_tvmaze(titel):
    """Openbare API zonder sleutel. Alleen succesvolle antwoorden worden gecachet."""
    response = requests.get("https://api.tvmaze.com/search/shows", params={"q": titel}, timeout=12)
    response.raise_for_status()
    rijen = []
    for hit in response.json():
        show = hit["show"]
        premiere = show.get("premiered")
        rijen.append({
            "titel_sleutel": normaliseer(show["name"]), "API-titel": show["name"],
            "release_year": int(premiere[:4]) if premiere else None,
            "TVmaze-id": show["id"], "TVmaze-score": show.get("rating", {}).get("average"),
            "Taal": show.get("language"), "Status": show.get("status"), "Bron": show["url"],
        })
    kolommen = ["titel_sleutel", "API-titel", "release_year", "TVmaze-id", "TVmaze-score", "Taal", "Status", "Bron"]
    return pd.DataFrame(rijen, columns=kolommen), datetime.now(timezone.utc).isoformat(timespec="seconds"), response.url


def toon_grafiek(fig):
    fig.update_layout(template="plotly_white", font=dict(size=14),
                      margin=dict(l=10, r=20, t=25, b=15), legend_title_text="",
                      legend=dict(orientation="h", y=1.12), height=390)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def getal(waarde):
    return f"{waarde:,.0f}".replace(",", ".")


def main():
    st.set_page_config(page_title="Netflix & Prime | Case 2", page_icon="🎬", layout="wide")
    st.markdown("""<style>
    .block-container {max-width:1250px;padding-top:3.5rem;padding-bottom:3rem;}
    h1 {letter-spacing:-1.5px;} h2 {letter-spacing:-0.5px;}
    [data-testid="stMetric"] {border:1px solid #dce3eb;border-radius:12px;padding:18px;}
    </style>""", unsafe_allow_html=True)
    st.caption("MINOR DATA SCIENCE · CASE 2 · CATALOGUSVERGELIJKING")
    st.title("Netflix versus Amazon Prime")
    st.write("**Welk platform past bij jouw kijkvoorkeur?** Vergelijk de omvang en samenstelling "
             "van het aanbod: films, series, genres, releasejaren en speelduur.")
    st.caption("Historische CSV-momentopnamen met releasejaren tot 2021. Dit dashboard toont geen actueel "
               "Nederlands aanbod, kijkcijfers of kwaliteitsoordeel. De precieze peildatum is niet in de CSV's vastgelegd.")

    try:
        data, raw, controles = laad_data()
    except (OSError, ValueError) as exc:
        st.error(f"De bronbestanden konden niet worden ingelezen: {exc}")
        st.stop()
    koppeling = koppel_catalogi(data)

    # 2. Alle hoofdanalyses gebruiken dezelfde filters.
    with st.sidebar:
        st.header("Maak je vergelijking")
        soort = st.selectbox("Type aanbod", ["Films en series", "Film", "Serie"])
        jaren = st.slider("Releasejaar", int(data.release_year.min()), int(data.release_year.max()),
                          (int(data.release_year.min()), int(data.release_year.max())))
        genre = st.selectbox("Genre", ["Alle genres"] + list(GENRES))
        percentage = st.checkbox("Vergelijk in percentages", value=True,
                                 help="De noemer is steeds het aantal gefilterde titels binnen hetzelfde platform.")
        st.caption("Rood = Netflix · Blauw = Amazon Prime. Filters gelden voor de grafieken, conclusies en titeltabel. "
                   "De dataverantwoording gebruikt altijd de volledige bronbestanden.")

    selectie = data[data.release_year.between(*jaren)].copy()
    if soort != "Films en series":
        selectie = selectie[selectie.soort.eq(soort)]
    if genre != "Alle genres":
        selectie = selectie[selectie.genres.map(lambda waarden: genre in waarden)]
    st.caption(f"SELECTIE: {soort} · {jaren[0]}–{jaren[1]} · {genre}")
    overzicht, verdieping, titels, methode = st.tabs(["Overzicht", "Genres & speelduur", "Titels & API", "Data & methode"])
    maat = "Percentage" if percentage else "Aantal"
    aslabel = "Aandeel van geselecteerde titels (%)" if percentage else "Aantal titels"
    aantallen = selectie.groupby("platform").size().reindex(PLATFORMS, fill_value=0)

    with overzicht:
        if selectie.empty:
            st.info("Geen titels voor deze combinatie. Kies een ruimer jaarbereik of een ander genre.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Netflix · vermeldingen", getal(aantallen["Netflix"]))
            c2.metric("Amazon Prime · vermeldingen", getal(aantallen["Amazon Prime"]))
            overlap_selectie = koppel_catalogi(selectie)
            overlap = int(overlap_selectie._merge.eq("both").sum())
            c3.metric("Gedeelde titels in selectie", getal(overlap))
            st.caption("Aanbod en percentages tellen catalogusrijen. Titelvarianten blijven behouden; "
                       "de overlap telt unieke titel/type/jaar-combinaties. Zie Data & methode.")
            st.subheader("1. Hoe is het aanbod verdeeld?")
            verdeling = aantallen_per_categorie(selectie, "soort", ["Film", "Serie"])
            toon_grafiek(px.bar(verdeling, x="soort", y=maat, color="platform", barmode="group",
                                color_discrete_map=KLEUREN, labels={"soort": "Type aanbod", maat: aslabel},
                                hover_data={"Aantal": True, "Percentage": ":.1f"}))
            for platform in PLATFORMS:
                if aantallen[platform]:
                    aandeel = selectie.loc[selectie.platform.eq(platform), "soort"].eq("Film").mean() * 100
                    st.write(f"**{platform}:** {getal(aantallen[platform])} titels, waarvan {aandeel:.1f}% films "
                             f"en {100-aandeel:.1f}% series binnen deze selectie.")
                else:
                    st.info(f"{platform} heeft geen titels in deze selectie. Een percentage is daarom niet beschikbaar.")

            st.subheader("2. Uit welke jaren komen de titels?")
            jaarverdeling = aantallen_per_categorie(selectie, "release_year", list(range(jaren[0], jaren[1] + 1)))
            toon_grafiek(px.line(jaarverdeling, x="release_year", y=maat, color="platform",
                                 color_discrete_map=KLEUREN, labels={"release_year": "Releasejaar", maat: aslabel},
                                 hover_data={"Aantal": True, "Percentage": ":.2f"}))
            medianen = selectie.groupby("platform").release_year.median()
            st.write("**Mediaan releasejaar:** " + " · ".join(f"{p}: {y:g}" for p, y in medianen.items()) + ".")
            st.caption("Dit is de verdeling naar releasejaar van aanwezige titels, geen groei van de catalogus. "
                       "Bij series kan het bronjaar naar een later seizoen verwijzen.")
            st.subheader("Conclusie voor jouw selectie")
            if aantallen.nunique() == 1:
                st.write("Beide platforms hebben evenveel titels binnen deze selectie.")
            else:
                winnaar = aantallen.idxmax()
                st.write(f"**{winnaar} heeft {getal(abs(aantallen.iloc[0] - aantallen.iloc[1]))} meer titels** "
                         "binnen deze selectie. Bekijk de genres en speelduur om te bepalen welk aanbod beter bij je voorkeur past.")
            st.write(f"We vinden **{getal(overlap)} gedeelde titels** die aan de filters voldoen in beide datasets. "
                     "Een groter aanbod betekent niet automatisch betere films of series.")

    with verdieping:
        st.subheader("3. Welke genres komen relatief vaak voor?")
        st.caption("Eigen indeling in tien vergelijkbare genregroepen. Eén titel kan in meerdere groepen vallen, "
                   "maar telt per groep maximaal één keer. Percentages tellen dus niet op tot 100%.")
        if selectie.empty:
            st.info("Geen titels voor deze filters.")
        else:
            lang = selectie.explode("genres").dropna(subset=["genres"])
            genre_tabel = aantallen_per_categorie(lang, "genres", list(GENRES))
            # Na explode moet de noemer het aantal titels blijven, niet het aantal genrevermeldingen.
            genre_tabel["Percentage"] = 100 * genre_tabel.Aantal / genre_tabel.platform.map(aantallen).replace(0, float("nan"))
            volgorde = genre_tabel.groupby("genres").Aantal.sum().sort_values().index.tolist()
            fig = px.bar(genre_tabel, y="genres", x=maat, color="platform", barmode="group", orientation="h",
                         color_discrete_map=KLEUREN, category_orders={"genres": volgorde[::-1]},
                         labels={"genres": "Genregroep", maat: aslabel}, hover_data={"Aantal": True, "Percentage": ":.1f"})
            toon_grafiek(fig)
            dekking = selectie.groupby("platform").genres.apply(lambda s: s.map(bool).mean() * 100)
            st.caption("Minstens één van deze genregroepen: " + " · ".join(f"{p}: {v:.1f}%" for p, v in dekking.items()) +
                       ". Overige bronlabels blijven beschikbaar in de titeltabel. Genrelabels verschillen per bron.")
            if (aantallen > 0).all():
                verschillen = genre_tabel.pivot(index="genres", columns="platform", values="Percentage")
                verschil = verschillen["Netflix"] - verschillen["Amazon Prime"]
                grootste = verschil.abs().idxmax()
                st.write(f"**Grootste verschil:** {grootste}, {abs(verschil[grootste]):.1f} procentpunt hoger bij "
                         f"{'Netflix' if verschil[grootste] >= 0 else 'Amazon Prime'} binnen deze selectie.")

            st.subheader("4. Hoe lang duurt een film of serie?")
            for label, kolom, eenheid in [("Film", "minuten", "Speelduur (minuten)"), ("Serie", "seizoenen", "Aantal seizoenen")]:
                subset = selectie[selectie.soort.eq(label)]
                geldig = subset.dropna(subset=[kolom])
                if subset.empty:
                    continue
                st.markdown(f"**{label}s**")
                if geldig.empty:
                    st.info("Geen geldige duur beschikbaar voor deze selectie.")
                    continue
                toon_grafiek(px.box(geldig, x="platform", y=kolom, color="platform", points="outliers",
                                     color_discrete_map=KLEUREN, labels={"platform": "Platform", kolom: eenheid},
                                     hover_data=["title"]))
                samenvatting = geldig.groupby("platform")[kolom].agg(Aantal="count", Mediaan="median", Gemiddelde="mean").round(1)
                st.dataframe(samenvatting, width="stretch")
                st.caption(f"{len(geldig)} van {len(subset)} titels hebben een geldige duur. "
                           "De lijn in de box is de mediaan; de box bevat de middelste 50%. "
                           "Seizoenen zijn geen kijkuren en staan los van de minuten bij films.")

    with titels:
        st.subheader("5. Welk aanbod delen de platforms?")
        st.caption("Strikte koppeling op genormaliseerde titel + type + releasejaar. Alternatieve titels en "
                   "verschillende seizoensjaren kunnen onterecht als verschillend tellen. 'Alleen' betekent uitsluitend in deze bestanden.")
        # Gebruik de volledige cataloguskoppeling om een titel niet door een genrefilter 'exclusief' te maken.
        geselecteerde_sleutels = selectie[SLEUTEL].drop_duplicates()
        lijst = koppeling.merge(geselecteerde_sleutels, on=SLEUTEL, how="inner", validate="one_to_one")
        aanbod = st.selectbox("Aanwezig in de bronbestanden", ["Alle titels", "In beide datasets", "Alleen in Netflix-dataset", "Alleen in Amazon-dataset"])
        zoek = st.text_input("Zoek een titel", placeholder="Bijvoorbeeld: The Untamed")
        if aanbod != "Alle titels":
            lijst = lijst[lijst.Aanbod.eq(aanbod)]
        lijst = lijst[lijst.Titel.str.contains(zoek, case=False, regex=False, na=False)]
        uitvoer = lijst[["Titel", "type", "release_year", "Aanbod"]].rename(columns={"type": "Type", "release_year": "Releasejaar"}).sort_values("Titel")
        st.caption(f"{getal(len(uitvoer))} gevonden titels. Deze tabel toont aanwezigheid in de volledige broncatalogi.")
        st.dataframe(uitvoer, hide_index=True, width="stretch")
        st.download_button("Download deze titelselectie", uitvoer.to_csv(index=False).encode("utf-8-sig"), "titelselectie.csv", "text/csv")
        with st.expander("Brongegevens en oorspronkelijke genrelabels bij deze titels"):
            details = selectie.merge(lijst[SLEUTEL], on=SLEUTEL, how="inner", validate="many_to_one")
            st.dataframe(details[["platform", "title", "type", "release_year", "listed_in", "duration", "rating"]],
                         hide_index=True, width="stretch")

        st.subheader("6. Een serie nader bekijken met de openbare TVmaze-API")
        st.write("De app haalt zelf aanvullende seriegegevens op. We koppelen alleen bij precies één overeenkomst "
                 "op titel én jaar. Een afwijkend seizoenjaar of alternatieve naam levert bewust geen automatische match op.")
        series = selectie.loc[selectie.soort.eq("Serie"), ["title", "titel_sleutel", "release_year"]].drop_duplicates(["titel_sleutel", "release_year"]).sort_values("title").reset_index(drop=True)
        if series.empty:
            st.info("Kies in de zijbalk series of films en series om de API te gebruiken.")
        else:
            standaard = series.index[series.title.eq("The Queen's Gambit")].tolist()
            keuze = st.selectbox("Serie voor API-verrijking", series.index.tolist(), index=standaard[0] if standaard else 0,
                                format_func=lambda i: f"{series.loc[i, 'title']} ({int(series.loc[i, 'release_year'])})")
            gekozen = series.loc[keuze]
            try:
                api, tijdstip, url = haal_tvmaze(gekozen.title)
                match = api[api.titel_sleutel.eq(gekozen.titel_sleutel) & api.release_year.eq(gekozen.release_year)]
                basis = selectie[selectie.titel_sleutel.eq(gekozen.titel_sleutel) & selectie.release_year.eq(gekozen.release_year) & selectie.soort.eq("Serie")]
                if len(match) == 1:
                    verrijkt = basis[["platform", "title", "titel_sleutel", "release_year"]].merge(
                        match, on=["titel_sleutel", "release_year"], how="left", validate="many_to_one")
                    st.dataframe(verrijkt[["platform", "title", "TVmaze-score", "Taal", "Status"]], hide_index=True, width="stretch")
                    st.caption(f"Left join: {len(basis)} catalogusrij(en) + {len(match)} API-match → {len(verrijkt)} rij(en). "
                               f"Opgehaald (UTC): {tijdstip}. Cache: 24 uur.")
                    st.markdown(f"[Serie op TVmaze]({match.iloc[0]['Bron']})")
                else:
                    st.info(f"{len(match)} eenduidige titel/jaar-kandidaten: er is geen automatische koppeling uitgevoerd. "
                            "De catalogusgegevens blijven behouden.")
                    st.dataframe(api.drop(columns=["titel_sleutel"]).rename(columns={"release_year": "Premièrejaar"}), hide_index=True)
                st.caption("TVmaze-scores en status zijn actuele aanvullende gegevens, geen representatieve vergelijking "
                           "van platformkwaliteit. Een score ontbreekt als TVmaze geen score teruggeeft.")
                st.markdown(f"[Gebruikt API-verzoek]({url}) · [TVmaze API / CC BY-SA](https://www.tvmaze.com/api)")
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                st.warning(f"TVmaze is momenteel niet beschikbaar ({type(exc).__name__}). "
                           "Alle CSV-analyses blijven werken. Probeer de API later opnieuw.")

    with methode:
        st.subheader("Onderzoeksvraag en werkwijze")
        st.write("We vergelijken de omvang en samenstelling van twee historische catalogi. Zoals in case 1 "
                 "beginnen we met een datacheck, maken we afgeleide variabelen en onderbouwen we conclusies met grafieken. "
                 "Er is geen voorspelmodel nodig om deze beschrijvende onderzoeksvraag te beantwoorden.")
        st.subheader("Bronnen en dataverzameling")
        st.markdown("- [Netflix Movies and TV Shows – Shivam Bansal, Kaggle](https://www.kaggle.com/datasets/shivamb/netflix-shows)\n"
                    "- [Amazon Prime Movies and TV Shows – Shivam Bansal, Kaggle](https://www.kaggle.com/datasets/shivamb/amazon-prime-movies-and-tv-shows)\n"
                    "- [TVmaze openbare API](https://www.tvmaze.com/api): `GET /search/shows?q=<titel>`; "
                    "velden `id`, `name`, `premiered`, `rating.average`, `language`, `status`, `url`.")
        st.write("De twee aangeleverde CSV's zijn vaste bronbestanden in de repository. Ze worden niet als API-download "
                 "voorgesteld. TVmaze wordt automatisch in Python opgevraagd en aan de geselecteerde serie gekoppeld. "
                 "API-uitkomsten kunnen veranderen; het ophaaltijdstip staat bij de resultaten.")
        st.subheader("Datacheck op de volledige bronbestanden")
        st.dataframe(controles.set_index("Platform").T, width="stretch")
        st.write("Na normalisatie zijn er 4 extra Netflix-rijen en 8 extra Amazon-rijen met dezelfde titel/type/jaar-sleutel. "
                 "Sommige hebben verschillende genres of speelduur en kunnen verschillende uitgaven beschrijven. "
                 "Daarom blijven ze in de aanbodanalyse staan als aparte catalogusvermeldingen. Alleen voor de overlap "
                 "tellen we elke sleutel één keer. Dat betekent dat de aanbodtotalen geen exacte aantallen unieke werken zijn.")
        ontbrekend = pd.DataFrame({p: frame.isna().mean() * 100 for p, frame in raw.items()})
        st.markdown("**Ontbrekende waarden vóór opschonen (%)**")
        st.dataframe(ontbrekend.round(1), width="stretch")
        st.write("Amazon mist bij ongeveer 93% een land en bij ongeveer 98% een toevoegdatum. Daarom gebruiken we "
                 "die velden niet voor een platformranglijst of groeianalyse. We vullen ontbrekende waarden niet in met nul. "
                 "Nul minuten is geen geldige speelduur. De drie verkeerd geplaatste Netflix-speelduren worden hersteld. "
                 "Leeftijdsclassificaties zijn geen kijkersscores en verschillen in systeem per platform.")
        st.subheader("Samenvoegen zonder onbedoelde vermenigvuldiging")
        beide = int(koppeling._merge.eq("both").sum())
        st.write(f"Verticaal samenvoegen met `concat`: {len(raw['Netflix'])} + {len(raw['Amazon Prime'])} ruwe rijen "
                 f"worden {len(data)} opgeschoonde platform-titelrijen. Een titel op twee platforms mag hier twee keer voorkomen.")
        st.write(f"Voor de cataloguskoppeling maken we per platform de sleutel uniek en doen een `outer merge`: "
                 f"{len(data[data.platform.eq('Netflix')].drop_duplicates(SLEUTEL))} Netflix-sleutels + "
                 f"{len(data[data.platform.eq('Amazon Prime')].drop_duplicates(SLEUTEL))} Amazon-sleutels − "
                 f"{beide} overeenkomsten = {len(koppeling)} rijen. `validate='one_to_one'` voorkomt een many-to-many-join.")
        st.code("sleutel = ['titel_sleutel', 'type', 'release_year']\n"
                "netflix.merge(amazon, on=sleutel, how='outer', validate='one_to_one')", language="python")
        st.caption("show_id begint in beide bestanden opnieuw bij s1 en is daarom geen gezamenlijke sleutel. "
                   "Titel/jaar is ook geen wereldwijd unieke identifier: de gevonden overlap is een benadering, geen bewezen exclusiviteit.")
        with st.expander("Bekijk de volledige genre-indeling"):
            st.dataframe(pd.DataFrame([{"Genregroep": groep, "Bronlabels": ", ".join(labels)} for groep, labels in GENRES.items()]), hide_index=True)
        st.subheader("Waarom deze grafieken?")
        st.write("Gegroepeerde staven zetten de platforms naast elkaar. Percentages corrigeren voor catalogusgrootte. "
                 "De lijngrafiek ordent releasejaren chronologisch. Boxplots vergelijken spreiding en medianen zonder "
                 "minuten en seizoenen door elkaar te halen. Filters en conclusies gebruiken dezelfde selectie.")
        st.subheader("Documentatie bij de code")
        st.markdown("[Streamlit](https://docs.streamlit.io/develop/api-reference) · "
                    "[pandas merge](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html) · "
                    "[Plotly Express](https://plotly.com/python/plotly-express/) · "
                    "[TVmaze API](https://www.tvmaze.com/api)")
        st.caption()
        


if __name__ == "__main__":
    main()


