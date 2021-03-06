# encoding: utf-8

import array
import base64
import datetime
import hashlib
import hmac
import json
import requests
import random
import string
import xmltodict

from urllib.parse import urlparse, urlencode


class Zanox():

    hostname = 'api.zanox.com'
    format = 'json'
    version = '2011-03-01'
    ssl = 'True'
    protocol = 'https'
    user_agent = 'Bot/Diadedesconto.com'
    datetime_format = '%a, %d %b %Y %H:%M:%S GMT'
    tracking_url_format = 'http://ad.zanox.com/ppc/?{tracking_id}&ULP=[[{destination}]]&zpar9=[[{connect_id}]]'

    def __init__(self, connect_id, secret_key, from_email=None, *args, **kwargs):

        self.connect_id = connect_id
        self.secret_key = secret_key
        self.from_email = from_email

        for key, value in kwargs.items():
            setattr(self, key, value)

    def construct_url(self, resource, **parameters):

        url_kwargs = {
            'protocol': self.protocol,
            'hostname': self.hostname,
            'format': self.format,
            'version': self.version,
            'resource': resource.strip('/'),
        }

        url = '{protocol}://{hostname}/{format}/{version}/{resource}'.format(**url_kwargs)
        if parameters:
            url = '?'.join((url, urlencode(parameters)))
        return url

    def extract_uri_from_url(self, url):

        url_parts = urlparse(url)
        uri = url_parts.path.split(self.version)[-1]
        return uri

    def get_default_headers(self):

        headers = {'User-Agent': self.user_agent}
        if self.from_email:
            headers['From'] = self.from_email
        return headers

    def extract_destination_url_from_tracking_url(self, tracking_url, clean=False):

        headers = self.get_default_headers()
        response = requests.head(tracking_url, allow_redirects=True, headers=headers)

        destination_url = response.url
        if 'adfarm.mediaplex.com' in response.url:
            query = urlparse(destination_url).query
            destination_url = query.split('mpro=')[-1]

        if clean:
            url_parts = urlparse(destination_url)
            destination_url = '{0}://{1}{2}'.format(url_parts.scheme, url_parts.netloc, url_parts.path)
        return destination_url

    def get_signature(self, url, method, date, nonce):

        # Construct signature
        uri = self.extract_uri_from_url(url)
        date = date.strftime(self.datetime_format)
        method = method.upper()
        elements = (method, uri, date, nonce)
        signature = u''.join(elements)

        # Encode signature SHA256, and Base64
        signature = hmac.new(bytearray(str.encode(self.secret_key)), msg=signature.encode('utf-8'), digestmod=hashlib.sha1).digest()
        signature = base64.b64encode(signature)
        signature = '%s:%s' % (self.connect_id, signature.decode("utf-8"))
        return signature

    @staticmethod
    def get_nonce(length=32, characters=string.ascii_uppercase + string.ascii_lowercase + string.digits):

        return ''.join(random.choice(characters) for item in range(length))

    def get_authenticated_headers(self, url, method):

        # format datetime
        date = datetime.datetime.utcnow()
        nonce = self.get_nonce()
        signature = self.get_signature(url, 'GET', date, nonce)
        headers = dict(self.get_default_headers())
        headers.update({
            'Authorization': "ZXWS {0}".format(signature),
            'Date': date.strftime(self.datetime_format),
            'nonce': nonce,
        })
        return headers

    @staticmethod
    def get_page_numbers(json):

        number_of_pages = int(json['total'] / json['items'])
        page_numbers = range(number_of_pages+1)
        return page_numbers

    def pretty_print(self, json_object):
        print(json.dumps(json_object, indent=4, sort_keys=True))

    def get(self, resource, **parameters):
        url = self.construct_url(resource, **parameters)
        headers = self.get_authenticated_headers(url, method='GET')
        response = requests.get(url, headers=headers)
        if self.format == 'json':
            return response.json()
        return response

    def get_program_identifier(self, tracking_url):
        return tracking_url.lower().split('&ulp')[0].split('ppc/?')[1]

    def get_tracking_url(self, destination_url, adspace_id=None, program_id=None, tracking_id=None, use_deeplink_generator=True):
        """Get a tracking url for a given destination url and adspace id"""

        if use_deeplink_generator:
            # Generate the link with de API
            if not adspace_id:
                raise Exception("`adspace_id` is required when you use the deeplink generator")
            deeplink_api_url = '{0}://toolbox.zanox.com/tools/api/deeplink?connectid={1}&adspaceid={2}&programid={3}&url={4}'.format(self.protocol, self.connect_id, adspace_id, program_id, destination_url)
            headers = self.get_authenticated_headers(deeplink_api_url, method='GET')
            response = requests.get(deeplink_api_url, headers=headers)
            tracking_url = xmltodict.parse(response.text)['deeplink']['url']
        else:
            # Generate the link with the given trakcing url format
            if not tracking_id:
                raise Exception("`tracking_id` is required when you use the deeplink generator")
            tracking_url_parameters = {
                'tracking_id': tracking_id,
                'connect_id': self.connect_id,
                'destination': destination_url
            }
            tracking_url = self.tracking_url_format.format(**tracking_url_parameters)
        return tracking_url


class Profile(Zanox):

    def get_profiles(self, **parameters):
        """
            doc: https://developer.zanox.com/web/guest/publisher-api-2011/get-profiles
        """
        return self.get('profiles', **parameters)


class AdSpace(Zanox):

    def get_ad_spaces(self, **parameters):
        """
            doc: https://developer.zanox.com/web/guest/publisher-api-2011/get-adspaces
        """
        return self.get('adspaces', **parameters)


class AdMedia(Zanox):
    pass


class Incentives(Zanox):

    def get_incentives(self, **parameters):
        """
            doc: https://developer.zanox.com/web/guest/publisher-api-2011/get-incentives
            parameters: {
                program,
                adspace,
                incentiveType
                region,
                items,
                page
            }
        """
        return self.get('incentives', **parameters)

    def get_incentives_incentive(self, **parameters):
        """
            doc: https://developer.zanox.com/web/guest/publisher-api-2011/get-incentives-incentive
            parameters: {
                adspace
            }
        """
        resource = "incentives/incentive/{0}".format(parameters['incentive_id'])
        return self.get(resource, **parameters)


class Product(Zanox):

    def get_products(self, **parameters):
        """
            doc: https://developer.zanox.com/web/guest/publisher-api-2011/get-products
            parameters: {
                q,
                searchtype,
                region,
                minprice,
                maxprice,
                programs,
                category,
                hasimages,
                adspace,
                partnership,
                ean,
                merchantcategory,
                items,
                page,
            }
        """
        return self.get('products', **parameters)

    def get_products_product(self, product_id, **parameters):
        """
            doc: https://developer.zanox.com/web/guest/publisher-api-2011/get-products-product
            parameters: {
                product,
                adspace
            }
        """
        resource = "products/product/{0}".format(product_id)
        return self.get(resource, **parameters)


class Reports(Zanox):
    pass


class Programs(Zanox):

    def get_programs(self, **parameters):
        """
            doc: https://developer.zanox.com/web/guest/publisher-api-2011/get-programs
            parameters: {
                q,
                startdate,
                region,
                partnership,
                category,
                industry,
                isexclusive,
                hasproducts,
                items,
                page
            }
        """
        return self.get('programs', **parameters)

    def get_programs_program(self, **parameters):
        """
            doc: https://developer.zanox.com/web/guest/publisher-api-2011/get-programs-program
            parameters: {
                id
            }
        """
        resource = "programs/program/{0}".format(parameters['id'])
        return self.get(resource, **parameters)

    def get_programs_categories(self, **parameters):
        """
            doc: https://developer.zanox.com/web/guest/publisher-api-2011/get-programs-categories
            parameters: {}
        """
        resource = ""
        return self.get('programs/categories', **parameters)


class ProgramAplications(Zanox):

    def get_programapplications(self, **parameters):
        """
            doc https://developer.zanox.com/web/guest/publisher-api-2011/get-programapplications
            parameters: {
                program,
                adspace,
                status,
                items,
                page
            }
        """
        return self.get('programapplications', **parameters)


class Tracking(Zanox):
    pass


class Balance(Zanox):
    pass