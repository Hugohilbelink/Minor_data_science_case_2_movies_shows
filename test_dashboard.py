"""Gerichte controles voor de analyse en de interactieve app: python -m unittest -v."""
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
import requests
from streamlit.testing.v1 import AppTest

import Dashboard_week_4 as dashboard


class AnalyseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.raw, cls.controles = dashboard.laad_data()

    def test_bronnen_en_join_reconciliatie(self):
        self.assertEqual(len(self.data), 8807 + 9668)
        samen = dashboard.koppel_catalogi(self.data)
        uniek = self.data.drop_duplicates(['platform'] + dashboard.SLEUTEL)
        overlap = samen['_merge'].eq('both').sum()
        self.assertEqual(overlap, 189)
        self.assertEqual(len(samen), len(uniek) - overlap)
        self.assertFalse(samen.duplicated(dashboard.SLEUTEL).any())

    def test_duur_en_genres(self):
        netflix = self.data[self.data.platform.eq('Netflix')]
        amazon = self.data[self.data.platform.eq('Amazon Prime')]
        self.assertEqual(netflix.loc[netflix.type.eq('Movie'), 'minuten'].isna().sum(), 0)
        self.assertEqual(amazon.loc[amazon.type.eq('Movie'), 'minuten'].isna().sum(), 10)
        self.assertTrue(self.data.loc[self.data.type.eq('TV Show'), 'minuten'].isna().all())
        self.assertEqual(dashboard.genre_groepen('Drama, Dramas, TV Dramas'), ['Drama'])
        self.assertEqual(dashboard.genre_groepen('Arts, Entertainment, and Culture, Kids'), ['Kinderen & familie'])

    def test_percentages_en_lege_groep(self):
        tabel = dashboard.aantallen_per_categorie(self.data, 'soort', ['Film', 'Serie'])
        self.assertTrue(tabel.groupby('platform').Percentage.sum().round(8).eq(100).all())
        alleen_netflix = self.data[self.data.platform.eq('Netflix')]
        tabel = dashboard.aantallen_per_categorie(alleen_netflix, 'soort', ['Film', 'Serie'])
        self.assertTrue(tabel.loc[tabel.platform.eq('Amazon Prime'), 'Percentage'].isna().all())

    def test_leeftijdslabels_en_ontbrekende_waarden(self):
        tabel = dashboard.aantallen_per_categorie(self.data, 'Classificatie')
        self.assertTrue(tabel.groupby('platform').Aantal.sum().eq(self.data.groupby('platform').size()).all())
        self.assertTrue(tabel.groupby('platform').Percentage.sum().round(8).eq(100).all())
        netflix = self.data[self.data.platform.eq('Netflix')]
        self.assertEqual(netflix.Classificatie.eq('Ontbreekt').sum(), 7)
        self.assertFalse(self.data.Classificatie.str.contains(' min').any())
        self.assertTrue({'NR', 'TV-MA', '18+', 'Ontbreekt'}.issubset(set(self.data.Classificatie)))

    def test_taalsteekproef_is_herhaalbaar_en_uniek(self):
        eerste = dashboard.kies_taalsteekproef(self.data)
        tweede = dashboard.kies_taalsteekproef(self.data)
        pd.testing.assert_frame_equal(eerste, tweede)
        self.assertEqual(eerste.groupby('platform').size().to_dict(), {'Amazon Prime': 150, 'Netflix': 150})
        self.assertFalse(eerste.duplicated(['platform'] + dashboard.SLEUTEL).any())
        self.assertTrue(eerste.type.eq('TV Show').all())

    def test_taalmatch_vereist_een_kandidaat_en_juist_jaar(self):
        kandidaten = pd.DataFrame([{'titel_sleutel': 'test', 'release_year': 2020,
                                    'Taal': 'English', 'TVmaze-id': 1, 'Bron': 'https://www.tvmaze.com/shows/1'}])
        self.assertEqual(dashboard.beoordeel_taalmatch(kandidaten, 'test', 2020)['Taal'], 'English')
        self.assertEqual(dashboard.beoordeel_taalmatch(kandidaten, 'test', 2019)['Koppelstatus'], 'Geen titel/jaarmatch')
        self.assertEqual(dashboard.beoordeel_taalmatch(pd.concat([kandidaten, kandidaten]), 'test', 2020)['Koppelstatus'], 'Meerdere matches')
        kandidaten['Taal'] = None
        self.assertEqual(dashboard.beoordeel_taalmatch(kandidaten, 'test', 2020)['Koppelstatus'], 'Taal onbekend')

    def test_taaldekking_en_noemers(self):
        selectie = pd.DataFrame({'platform': ['Netflix'] * 3 + ['Amazon Prime'],
                                 'titel_sleutel': ['a', 'b', 'c', 'd'], 'type': ['TV Show'] * 4,
                                 'release_year': [2020] * 4})
        api = pd.DataFrame({'platform': ['Netflix', 'Netflix', 'Amazon Prime'],
                            'titel_sleutel': ['a', 'b', 'd'], 'release_year': [2020] * 3,
                            'Koppelstatus': ['Gekoppeld', 'Geen titel/jaarmatch', 'API-fout'],
                            'Taal': ['English', None, None]})
        sample, bekend, dekking = dashboard.taaloverzicht(selectie, api)
        self.assertEqual(dekking.loc['Netflix'].to_list(), [3, 2, 1, 1, 50])
        self.assertEqual(len(sample), 3)
        self.assertEqual(len(bekend), 1)
        tabel = dashboard.aantallen_per_categorie(bekend, 'Taal')
        self.assertEqual(tabel[tabel.platform.eq('Netflix')].Percentage.iloc[0], 100)
        self.assertTrue(tabel[tabel.platform.eq('Amazon Prime')].Percentage.isna().all())
        sample, bekend, dekking = dashboard.taaloverzicht(selectie.iloc[0:0], api)
        self.assertTrue(sample.empty)
        self.assertTrue(dekking['Matchdekking (%)'].isna().all())



class AppTests(unittest.TestCase):
    def test_filters_en_api_storing(self):
        # Geen netwerk nodig: simuleer een API-storing en controleer de CSV-app volledig.
        dashboard.haal_tvmaze.clear()
        with patch('requests.get', side_effect=requests.ConnectionError('test offline')):
            app = AppTest.from_file(str(Path(__file__).with_name('Dashboard_week_4.py')), default_timeout=30).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.metric[0].value, '8.807')
            self.assertTrue(any('TVmaze' in w.value for w in app.warning))
            app.sidebar.selectbox[0].select('Film').run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.metric[0].value, '6.131')
            self.assertEqual(app.metric[1].value, '7.814')
            app.sidebar.checkbox[0].uncheck().run()
            self.assertEqual(len(app.exception), 0)
            # Oudste jaartal heeft alleen Amazon: ontbrekend platform geeft geen crash.
            app.sidebar.slider[0].set_range(1920, 1920).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.metric[0].value, '0')
            # Geen anime in dit jaar: lege selectie moet begrijpelijke uitleg tonen.
            app.sidebar.selectbox[1].select('Anime').run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any('Geen titels' in i.value for i in app.info))


if __name__ == '__main__':
    unittest.main()
