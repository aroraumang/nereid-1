# This file is part of Tryton & Nereid. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import activate_module, USER, with_transaction
from trytond.pool import Pool
from trytond.transaction import Transaction
from nereid.testing import NereidTestCase
from nereid.exceptions import WebsiteNotFound


class TestRouting(NereidTestCase):
    'Test URL Routing'

    def setUp(self):
        activate_module('nereid_test')

        self.templates = {
            'home.jinja': '{{ Transaction().language }}',
        }

    def setup_defaults(self):
        """
        Setup the defaults
        """
        self.nereid_website_obj = Pool().get('nereid.website')
        self.locale_obj = Pool().get('nereid.website.locale')
        self.nereid_user_obj = Pool().get('nereid.user')
        self.company_obj = Pool().get('company.company')
        self.language_obj = Pool().get('ir.lang')
        self.currency_obj = Pool().get('currency.currency')
        self.country_obj = Pool().get('country.country')
        self.subdivision_obj = Pool().get('country.subdivision')
        self.party_obj = Pool().get('party.party')

        self.usd, self.eur = self.currency_obj.create([{
            'name': 'US Dollar',
            'code': 'USD',
            'symbol': '$',
        }, {
            'name': 'Euro',
            'code': 'EUR',
            'symbol': 'E',
            'rates': [('create', [{'rate': Decimal('2')}])],
        }])
        self.party, = self.party_obj.create([{
            'name': 'Openlabs',
        }])
        self.company, = self.company_obj.create([{
            'party': self.party,
            'currency': self.usd,
        }])
        party, = self.party_obj.create([{
            'name': 'Registered User',
        }])
        self.registered_user, = self.nereid_user_obj.create([{
            'party': party,
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': self.company,
        }])

        self.en_us, = self.language_obj.search([('code', '=', 'en')])
        self.es_es, = self.language_obj.search([('code', '=', 'es')])
        self.locale_en_us, self.locale_es_es = self.locale_obj.create([{
            'code': 'en_US',
            'language': self.en_us,
            'currency': self.usd,
        }, {
            'code': 'es_ES',
            'language': self.es_es,
            'currency': self.eur,
        }])

        self.nereid_website, = self.nereid_website_obj.create([{
            'name': 'localhost',
            'company': self.company,
            'application_user': USER,
            'default_locale': self.locale_en_us,
            'locales': [('add', [self.locale_en_us.id, self.locale_es_es.id])],
        }])

    def get_template_source(self, name):
        """
        Return templates
        """
        return self.templates.get(name)

    def get_app(self):
        """
        Inject transaction into the template context for the home template
        """
        app = super(TestRouting, self).get_app()
        app.jinja_env.globals['Transaction'] = Transaction
        return app

    @with_transaction()
    def test_0010_home_with_locales(self):
        """
        When accessing / for website with locales defined, there should be a
        redirect to the /locale
        """
        self.setup_defaults()
        app = self.get_app()

        with app.test_client() as c:
            response = c.get('/')
            self.assertEqual(response.status_code, 301)
            self.assertEqual(
                response.location,
                'http://localhost/%s' % self.locale_en_us.code
            )

        # Change the default locale to es_ES and then check
        self.nereid_website.default_locale = self.locale_es_es
        self.nereid_website.save()
        self.nereid_website.clear_url_adapter_cache()

        app = self.get_app()

        with app.test_client() as c:
            response = c.get('/')
            self.assertEqual(response.status_code, 301)
            self.assertEqual(
                response.location,
                'http://localhost/%s' % self.locale_es_es.code
            )

    @with_transaction()
    def test_0020_home_without_locales(self):
        """
        When accessed without locales the site should return 200 on /
        """
        self.setup_defaults()

        # unset the locales
        self.nereid_website.locales = []
        self.nereid_website.save()

        app = self.get_app()

        with app.test_client() as c:
            response = c.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'en')

    @with_transaction()
    def test_0030_lang_context_with_locale(self):
        """
        Test that the language available in the context is the right one
        """
        self.setup_defaults()
        app = self.get_app()

        with app.test_client() as c:
            response = c.get('/en_US/')
            self.assertEqual(response.data, b'en')

        with app.test_client() as c:
            response = c.get('/es_ES/')
            self.assertEqual(response.data, b'es')

    @with_transaction()
    def test_0040_lang_context_without_locale(self):
        """
        Test that the language available in the context is the right one
        """
        self.setup_defaults()
        self.nereid_website.locales = []
        self.nereid_website.save()
        app = self.get_app()

        with app.test_client() as c:
            response = c.get('/')
            self.assertEqual(response.data, b'en')

        # Change the default locale to es_ES and then check
        self.nereid_website.default_locale = self.locale_es_es
        self.nereid_website.save()

        with app.test_client() as c:
            response = c.get('/')
            self.assertEqual(response.data, b'es')

    @with_transaction()
    def test_0050_website_routing(self):
        """
        Test should not check for match on single website.
        """
        self.setup_defaults()
        self.nereid_website.locales = []
        self.nereid_website.save()
        app = self.get_app()

        with app.test_client() as c:
            response = c.get('http://localhost/')
            self.assertEqual(response.data, b'en')

            response = c.get('http://this_should_work_too/')
            self.assertEqual(response.data, b'en')

            self.nereid_website_obj.create([{
                'name': 'another_website',
                'company': self.company,
                'application_user': USER,
                'default_locale': self.locale_en_us,
            }])

            # Should Break, As there are more than 1 website.
            self.assertRaises(
                WebsiteNotFound, c.get, 'http://this_should_break/'
            )

    @with_transaction()
    def test_0060_invalid_active_id_url(self):
        """
        Test that the url if 404 if record for active_id doesn't exist
        """
        self.setup_defaults()
        self.nereid_website.locales = []
        self.nereid_website.save()
        app = self.get_app()
        country, = self.country_obj.create([{
            'name': 'India',
            'code': 'IN'
        }])

        with app.test_client() as c:
            response = c.get('/countries/%d/subdivisions' % country.id)
            self.assertEqual(response.status_code, 200)

            response = c.get('/countries/6/subdivisions')  # Invalid record
            self.assertEqual(response.status_code, 404)

    @with_transaction()
    def test_0070_csrf(self):
        """
        Test that the csrf for POST request
        """
        self.setup_defaults()
        self.nereid_website.locales = []
        self.nereid_website.save()
        app = self.get_app()
        # Enable CSRF
        app.config['WTF_CSRF_ENABLED'] = True

        with app.test_client() as c:
            # NO csrf-token
            response = c.post('/test-csrf', data={
                'name': 'dummy name'
            })
            self.assertEqual(response.status_code, 400)

            # csrf token with invalid form
            csrf_token = c.get('/gen-csrf').data
            response = c.post('/test-csrf', data={
                'csrf_token': csrf_token,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'Failure')

            # csrf token with valid form
            csrf_token = c.get('/gen-csrf').data
            response = c.post('/test-csrf', data={
                'name': 'dummy name',
                'csrf_token': csrf_token,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'Success')

    @with_transaction()
    def test_0070_csrf_exempt(self):
        """
        Test that the csrf exempt for POST request
        """
        self.setup_defaults()
        self.nereid_website.locales = []
        self.nereid_website.save()
        app = self.get_app()
        # Enable CSRF
        app.config['WTF_CSRF_ENABLED'] = True

        with app.test_client() as c:
            # invalid form
            response = c.post('/test-csrf-exempt', data={
                'name': '',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'Failure')

            # valid form
            response = c.post('/test-csrf-exempt', data={
                'name': 'dummy name',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'Success')


def suite():
    "Nereid test suite"
    test_suite = unittest.TestSuite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestRouting)
    )
    return test_suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
