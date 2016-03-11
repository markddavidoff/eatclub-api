# coding=utf-8
#import logging
#logging.basicConfig(filename='scraper.log',level=logging.DEBUG)
import json
import os
from urlparse import urljoin

import scrapy
import logging

from scrapy.crawler import CrawlerProcess
from scrapy.http import Request
from scrapy.settings import Settings
from scrapy.utils.response import open_in_browser

"""
This is a super messy, first stab that I thought I'd toss up on github until/if
I come back to it
"""


##################################################################
# To authenticate,
# have a file 'credentials.txt' of the format:
# email=<email>
# password=<password>
##################################################################

EMAIL = None
PASS = None

if not os.path.exists('credentials.txt'):
    msg = 'credentials.txt file is missing!'
    print msg
    raise ValueError(msg)

with open('credentials.txt', 'r') as f:
    try:
        for line in f:
            if "email=" in line:
                EMAIL = line.split("=")[1]
            if "password=" in line:
                PASS = line.split("=")[1]
    except:
        print 'credentials.txt file is the wrong format!'
        raise



most_recent_order = []

class NutriInfoScraper(scrapy.Spider):

    name = 'nutriinfoscraper'
    start_urls = ["https://www.eatclub.com/login/"]

    def parse(self, response):
        # login first
        print "======= Logging in ======="
        yield scrapy.FormRequest.from_response(
            response,
            formdata={'email': EMAIL,
                      'password': PASS,
                      'next': '/',
                      'login-submit-btn': 'Login'
                        },
            callback=self.after_login
        )

    def after_login(self, response):
        if 'login' in response._url:
            msg = "======= Log in failed! ======="
            print msg
            raise RuntimeError(msg)

        print "======= Logged in ======="
        print "======= Getting Order History ======="
        yield Request(url="https://www.eatclub.com/orders/history/",
               callback=self.start_parsing)

    def start_parsing(self, response):
        print "======= Parsing Order History ======="
        # get just the most recent order
        orders = response.css('td.item a::attr(href)')
        if not orders or not orders[0]:
            msg = "Could not retrieve order history!"
            print msg
            #logging.error(msg)
            raise RuntimeError(msg)
        first_url = response.urljoin(orders[0].extract())
        yield Request(first_url, callback=self.parse_nutri_info)

    def parse_nutri_info(self, response):
        food_ids = response.css('#recipal_id::attr(data-recipal-id)')[0].extract().split(",")

        for id in food_ids:
            url = "https://www.eatclub.com/public/api/nutrition-info/{}/?format=json".format(str(id))
            yield Request(url=url, callback=self.on_food_nutri_response)

    def on_food_nutri_response(self, response):
        nutrition = json.loads(response.body_as_unicode())
        global most_recent_order
        recipe = nutrition['recipe']
        recipe['url'] = response._url
        most_recent_order.append(recipe)
        yield nutrition

    # this was for scraping the page. using api hack instead
    def scrape_nutri_info(self, response):
        meal = response.css('div[ng-controller=DishDetailsCtrl]')
        open_in_browser(response)
        foods = meal.css('.ng-scope')
        data = {}
        for food in foods:
            name = food.css('div.attribute.dish-name.ng-binding').extract().trim()
            # food_props = food.css('span.attribute-title ')
            food_props = food.css('.attribute .ng-binding :not(.ng-hide)')
            food_data = {}
            for prop in food_props:
                key = prop.css('span').extract().trim().replace(':', '')
                value = prop.extract().trim()
                food_data[key] = value
            name = food.css('.attribute .dish-name .ng-binding').extract().trim()

            data[name] = food_data
        yield data
        #names = response.css('div > div > div > div > div.attribute.dish-name.ng-binding')


# process = CrawlerProcess({
#     'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)'
# })
settings = Settings()
settings.set('FEED_FORMAT', 'json')
settings.set('FEED_URI', 'result.json')
settings.set('USER_AGENT', 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)')
settings.set('LOG_LEVEL', logging.CRITICAL)
process = CrawlerProcess(settings)
process.crawl(NutriInfoScraper)
process.start()


def print_nutrition_info(order_items):
    print "\nNutritional Info for Most Recent Order:\n"
    for item in order_items:
        print "{}".format(item['url'])
        print "{}".format(item['name'])
        print "{}".format(''.ljust(len(item['name']), "="))
        nutrition = item['nutrition']
        calories = nutrition.pop('calories')
        calories_from_fat = nutrition.pop('calories_from_fat')
        serving_size = nutrition.pop('serving_size')
        if serving_size:
            print "Servings: {}".format(str(serving_size))
        print "Calories: {}".format(str(int(calories)))
        print "Calories from Fat: {}".format(str(int(calories_from_fat)))
        units = {
            'micrograms': u'µg',
            'milligrams': 'mg',
            'grams': 'g',
            'iu': 'IU'
        }

        for k, v in nutrition.items():
            if v is not None:
                amount = str(int(v))
                words_in_name = [word.lower() for word in k.split("_")]
                for unit, sign in units.items():
                    unit_name = unit.lower()
                    if unit_name in words_in_name:
                        words_in_name.remove(unit_name)
                        amount += " " + unicode(sign)
                        break
                readable_name = " ".join(words_in_name).title()
                print u"{}: {}".format(readable_name, amount)

print_nutrition_info(most_recent_order)
