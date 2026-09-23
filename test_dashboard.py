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
