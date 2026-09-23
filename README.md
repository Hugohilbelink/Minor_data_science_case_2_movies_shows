# Netflix versus Amazon Prime — case 2

Interactief Streamlit-dashboard voor Minor Data Science. Alle appcode staat in **Dashboard_week_4.py**.

**[Open het dashboard](https://hugo-case2-netflix-prime.streamlit.app/)** ·
[GitHub-repository](https://github.com/Hugohilbelink/Minor_data_science_case_2_movies_shows)

## Onderzoeksvraag

Welk platform past bij jouw kijkvoorkeur, gezien de omvang en samenstelling van de catalogus?
We vergelijken films en series, releasejaren, vergelijkbare genregroepen, speelduur en gedeelde titels.
Daarnaast vergelijken we oorspronkelijke leeftijdsclassificaties en verkennen we hoofdtalen van gekoppelde series.
De aanpak sluit aan op case 1: vraag → data inladen → datacheck → afgeleide variabelen → grafieken → conclusies.

## Lokaal starten

Gebruik Python 3.12 of hoger. Voer in deze map uit:

```bash
python -m pip install -r requirements.txt
python -m streamlit run Dashboard_week_4.py
```

De twee CSV-bestanden staan naast het script. Bestandspaden worden afgeleid van `__file__`,
zodat starten vanuit een andere werkmap ook werkt. Er zijn geen API-sleutels of secrets nodig.
De API heeft een timeout en cache van 24 uur. Bij een netwerkstoring blijven alle CSV-analyses beschikbaar.

## Online publiceren

Open [Streamlit Community Cloud](https://share.streamlit.io), kies deze GitHub-repository,
branch `main`, en hoofdbestand `Dashboard_week_4.py`. Kies Python 3.12 of hoger bij Advanced settings.
`requirements.txt` installeert de dependencies automatisch. GitHub bewaart de code; Streamlit draait de app.
Zie de [officiële deploy-instructies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## Data en API

| Bron | Bestand / verzoek | Gebruik |
|---|---|---|
| [Netflix — Shivam Bansal / Kaggle](https://www.kaggle.com/datasets/shivamb/netflix-shows) | `netflix_titles.csv`, 8.807 rijen | Historische catalogus |
| [Amazon Prime — Shivam Bansal / Kaggle](https://www.kaggle.com/datasets/shivamb/amazon-prime-movies-and-tv-shows) | `amazon_prime_titles.csv`, 9.668 rijen | Historische catalogus |
| [TVmaze openbare API](https://www.tvmaze.com/api) | `GET https://api.tvmaze.com/search/shows?q=<titel>` | Aanvullende informatie over een geselecteerde serie |

De CSV's zijn de door de groep aangeleverde bestanden en worden ongewijzigd bewaard. De analyse is
een historische momentopname met releasejaren tot 2021. De exacte extractiedatum, markt en abonnementsvorm
zijn niet vastgelegd in de CSV's. Trek hieruit geen conclusie over het huidige Nederlandse aanbod.

De app haalt TVmaze-data automatisch in het script op, dus de openbare API-eis is daadwerkelijk geïmplementeerd.
Opgevraagde velden: `id`, `name`, `premiered`, `rating.average`, `language`, `status`, `url`.
Het verzoek en UTC-ophaaltijdstip staan in de app. De API-data vallen onder de TVmaze
[CC BY-SA-voorwaarden](https://www.tvmaze.com/api#licensing); TVmaze wordt in de app vermeld en gelinkt.
De CSV-analyse is reproduceerbaar met de vastgelegde bestanden; live API-scores kunnen veranderen.

## Analytische keuzes

- Eén rij is een catalogusvermelding. Beide bronbestanden worden met een platformkolom verticaal gecombineerd.
- Een aparte outer join op **genormaliseerde titel + type + releasejaar** vergelijkt de catalogi.
  `show_id` is niet platformoverstijgend uniek en mag hiervoor niet worden gebruikt.
- De normalisatie negeert hoofdletters, extra spaties en Unicode-presentatieverschillen, maar behoudt leestekens en accenten.
- Er zijn 4 extra Netflix- en 8 extra Amazon-rijen met een herhaalde genormaliseerde sleutel.
  Ze blijven in de aanbodanalyse, omdat onder andere genres en speelduur kunnen verschillen.
  Voor overlap wordt elke sleutel één keer geteld: 8.803 + 9.660 − 189 = **18.274 sleutels**.
- `validate='one_to_one'` voorkomt rijvermenigvuldiging bij de catalogusjoin.
  De TVmaze left join gebruikt `validate='many_to_one'` en alleen één exacte titel/jaar-kandidaat.
  Geen kandidaat of meerdere kandidaten betekent geen automatische koppeling; de app laat dat expliciet zien.
- Series kunnen in de CSV het jaar van een later seizoen hebben; TVmaze gebruikt het premièrejaar.
  Deze strikte methode mist daardoor echte overeenkomsten. Overlap is een benadering, geen bewijs van exclusiviteit.
- Percentages gebruiken per platform het gefilterde aantal catalogusrijen als noemer, ook na het uitsplitsen van genres.
  Eén titel kan meerdere genres hebben en telt per genregroep maximaal één keer.
- Tien inhoudelijk vergelijkbare genregroepen zijn handmatig vastgelegd in `GENRES`.
  Niet alle bronlabels zijn vergelijkbaar. De dekking en volledige indeling staan in de app.
- Drie Netflix-speelduren staan foutief in `rating`; ze worden hersteld. Tien Amazon-films hebben nul minuten;
  hun duur wordt onbekend, niet nul. Films (minuten) en series (seizoenen) worden apart geanalyseerd.
- Bij Amazon mist ongeveer 93% van `country` en 98% van `date_added`. Daarom geen landenranglijst of catalogusgroeicurve.
- `rating` in de CSV is een leeftijdsclassificatie, geen kijkerswaardering. TVmaze-scores van één geselecteerde serie
  onderbouwen geen platformbrede kwaliteitsranglijst.

## Opdracht en presentatie

### Leeftijdsclassificatie en talen

Het tabblad **Leeftijdsclassificatie** toont ieder oorspronkelijk label naast het andere platform.
De noemer is alle gefilterde catalogusvermeldingen per platform, inclusief ontbrekende waarden.
Lege classificaties heten `Ontbreekt`; `NR`, `UR`, `UNRATED`, `TV-NR` en `NOT_RATE` blijven apart herkenbaar.
De drie herstelde Netflix-speelduren tellen als ontbrekende classificatie (7 in totaal).
Labels zoals `TV-MA`, `R` en `18+` worden niet gelijkgesteld of omgezet naar Kijkwijzer.
Uitleg staat bij de grafiek met bronnen van [TV Parental Guidelines](https://www.tvguidelines.org/ratings.html)
en [MPA Film Ratings](https://www.filmratings.com/ratings-guide/).

Het tabblad **Talen** leest `tvmaze_talen.json`, een door het script opgehaalde API-momentopname.
Een vaste willekeurige steekproef van 150 unieke serie-titel/type/jaarcombinaties per platform
wordt vóór het matchen getrokken (`random_state=42`, stabiel gesorteerde invoer).
Alleen één exacte genormaliseerde titel/jaar-match met bekende taal gaat de grafiek in.
Geen match, meerdere matches, onbekende taal en API-fouten blijven in de dekkingscontrole staan.
De filters beperken deze bestaande steekproef; ze trekken geen nieuwe steekproef.
De percentagenoemer is uitsluitend het aantal gekoppelde steekproefseries met een bekende taal per platform.
Een nulnoemer blijft onbeschikbaar. De app toont daarnaast de volledige seriepopulatie binnen de filters,
steekproefomvang, bruikbare matches en matchdekking. Selectieve uitval kan taalverschillen vertekenen:
de grafiek is geen representatieve vergelijking van de volledige catalogi.

TVmaze `language` is de **belangrijkste gesproken taal**, niet het aanbod van ondertiteling of nasynchronisatie.
De JSON bevat per aanvraag het ophaaltijdstip, bron-URL en koppelstatus, plus SHA-256-controles van de CSV's.
Bij gewijzigde CSV's wordt de oude taalverdeling niet getoond. Deze data vallen onder TVmaze CC BY-SA;
bron en licentie staan in de app en in de JSON. Het eerdere tabblad Titels & API blijft live aanvragen doen.

De momentopname opnieuw ophalen (duurt enkele minuten, geen API-sleutel nodig):

```bash
python Dashboard_week_4.py --vernieuw-talen
```

Dit schrijft `tvmaze_talen.json` opnieuw met circa 1,5 aanvragen per seconde en retries bij HTTP 429.
Commit het vernieuwde bestand om de nieuwe resultaten online te tonen. Het dashboard zelf hoeft
bij openen geen honderden API-aanvragen te doen. Live API-resultaten kunnen na verloop van tijd veranderen.

### Presentatievoorstel

Gebaseerd op de aangeleverde pdf's `Case 2 - Streamlit dashboard` en `Hoe je case wordt beoordeeld`, onderdeel case 2.
De onderwijs-pdf's worden niet meegestuurd naar de publieke repository.

| Opdrachteis | Uitwerking |
|---|---|
| Openbare API in script | TVmaze, automatische aanvraag, cache, timeout, foutafhandeling, bronlink |
| Twee losse datasets combineren | CSV-concat, outer join en aanvullende API-left-join, met sleutels en rijtellingen |
| Dataverkenning | Ontbrekende waarden, duplicaten, bereiken, ongeldige duur en verantwoorde opschoning |
| Analyse en verhaal | Vraag, aanbodverdeling, releasejaren, genres, speelduur, overlap en dynamische conclusie |
| Slider, checkbox, dropdown | Releasejaar, aantallen/percentages, type en genre |
| Vergelijken en annoteren | Vaste platformkleuren, gelijke assen, uitleg/noemers en conclusies naast grafieken |
| Reproduceerbaar | Vastgelegde CSV's, requirements en geen verplichte secrets |

Voorstel voor een live presentatie van 9 minuten:

1. Vraag en bronnen (1 minuut).
2. Datakwaliteit en joins (2 minuten).
3. Aanbod, releasejaren en aantallen versus percentages (2 minuten).
4. Genre- en jaarfilters, speelduur (2 minuten).
5. Gedeelde titels, API-voorbeeld en conclusie met beperkingen (2 minuten).

De groep moet zelf controleren of het onderwerp tijdig via Teams is gemeld en de code kunnen uitleggen.
De pdf-verwijzing naar de volledige rubric op Brightspace kan aanvullende niveaucriteria bevatten.

## Controle uitvoeren

```bash
python -m unittest -v
```

Tests controleren joins en totalen, duurreparatie, genrededuplicatie, noemers, filters,
lege selecties, één ontbrekend platform en een API-storing. De test gebruikt hiervoor geen live API.

## Codebronnen

De code is met hulp van Codex opgesteld voor deze datasets. Gebruikte bibliotheekpatronen en documentatie:
[Streamlit](https://docs.streamlit.io/develop/api-reference),
[Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing),
[pandas merge](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html),
[Plotly Express](https://plotly.com/python/plotly-express/),
[TVmaze API](https://www.tvmaze.com/api).
