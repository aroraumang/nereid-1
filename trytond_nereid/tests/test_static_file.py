#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    test_static_file

    Test the static file feature of nereid

    :copyright: (c) 2012-2015 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details.
"""
import unittest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import (
    activate_module, USER, DB_NAME, with_transaction
)
from trytond.pool import PoolMeta, Pool
from trytond.config import config
from nereid.testing import NereidTestCase
from nereid import render_template, route

config.set('email', 'from', 'from@xyz.com')
config.set('database', 'path', '/tmp/temp_tryton_data/')


class StaticFileServingHomePage(metaclass=PoolMeta):
    __name__ = 'nereid.website'

    @classmethod
    @route('/static-file-test')
    def static_file_test(cls):
        static_file_obj = Pool().get('nereid.static.file')

        static_file, = static_file_obj.search([])
        return render_template(
            'home.jinja',
            static_file_obj=static_file_obj,
            static_file_id=static_file.id
        )


class TestStaticFile(NereidTestCase):

    @classmethod
    def setUpClass(cls):
        Pool.register(
            StaticFileServingHomePage,
            module='nereid', type_='model'
        )
        Pool(DB_NAME).init(update=['nereid'])

    @classmethod
    def tearDownClss(cls):
        mpool = Pool.classes['model'].setdefault('nereid', [])
        mpool.remove(StaticFileServingHomePage)
        Pool().init(update=['nereid'])

    def setUp(self):
        activate_module('nereid')

        self.templates = {
            'home.jinja':
            '''
            {% set static_file = static_file_obj(static_file_id) %}
            {{ static_file.url }}
            ''',
        }

    def setup_defaults(self):
        """
        Setup the defaults
        """
        self.nereid_website_obj = Pool().get('nereid.website')
        self.nereid_website_locale_obj = Pool().get('nereid.website.locale')
        self.nereid_user_obj = Pool().get('nereid.user')
        self.company_obj = Pool().get('company.company')
        self.currency_obj = Pool().get('currency.currency')
        self.language_obj = Pool().get('ir.lang')
        self.country_obj = Pool().get('country.country')
        self.subdivision_obj = Pool().get('country.subdivision')
        self.party_obj = Pool().get('party.party')
        self.address_obj = Pool().get('party.address')
        self.contact_mech_obj = Pool().get('party.contact_mechanism')
        self.static_file_obj = Pool().get('nereid.static.file')
        self.static_folder_obj = Pool().get('nereid.static.folder')

        usd, = self.currency_obj.create([{
            'name': 'US Dollar',
            'code': 'USD',
            'symbol': '$',
        }])
        self.party, = self.party_obj.create([{
            'name': 'Openlabs',
        }])
        self.company, = self.company_obj.create([{
            'party': self.party,
            'currency': usd,
        }])

        en_us, = self.language_obj.search([('code', '=', 'en')])
        currency, = self.currency_obj.search([('code', '=', 'USD')])
        locale, = self.nereid_website_locale_obj.create([{
            'code': 'en_US',
            'language': en_us,
            'currency': currency,
        }])
        self.nereid_website_obj.create([{
            'name': 'localhost',
            'company': self.company,
            'application_user': USER,
            'default_locale': locale,
            'locales': [('add', [locale.id])],
        }])

    def create_static_file(self, file_buffer):
        """
        Creates the static file for testing
        """
        folder_id, = self.static_folder_obj.create([{
            'name': 'test',
            'description': 'Test Folder'
        }])

        return self.static_file_obj.create([{
            'name': 'test.png',
            'folder': folder_id,
            'file_binary': file_buffer,
        }])[0]

    @with_transaction()
    def test_0010_static_file(self):
        """
        Create a static folder, and a static file
        And check if it can be fetched
        """
        self.setup_defaults()

        file_buffer = memoryview(b'test-content')
        static_file = self.create_static_file(file_buffer)
        self.assertEqual(static_file.file_binary, file_buffer)

        app = self.get_app()

        with app.test_client() as c:
            rv = c.get('/en_US/static-file/test/test.png')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, b'test-content')
            self.assertEqual(rv.headers['Content-Type'], 'image/png')

    @with_transaction()
    def test_0020_static_file_url(self):
        self.setup_defaults()

        file_buffer = memoryview(b'test-content')
        file = self.create_static_file(file_buffer)
        self.assertFalse(file.url)

        app = self.get_app()
        with app.test_client() as c:
            rv = c.get('/en_US/static-file-test')
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(b'/en_US/static-file/test/test.png' in rv.data)


def suite():
    "Nereid test suite"
    test_suite = unittest.TestSuite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestStaticFile)
    )
    return test_suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
