import csv
import threading
import time
import traceback
import datetime
from cStringIO import StringIO

# Bot libs
from modules.Configuration import FULL_LIST
from modules.Data import truncate
try:
    import numpy
    use_numpy = True
except ImportError as ex:
    ex.message = ex.message if ex.message else str(ex)
    print("WARN: Module Numpy not found, using manual percentile method instead. "
          "It is recommended to install Numpy. Error: {0}".format(ex.message))
    use_numpy = False

# TODO
# [x] Thread the market data writing
# [x] Make write times more deterministic
# [ ] Write to sqllite (people can use other DBs then if they like)
# [ ] Reduce the time in the config file to allow 1 sec
# [ ] Record more data (we can work out what to do with it later)
# [ ] Provide something that takes into account dust offers. (The golden cross works well on BTC, not slower markets)

# NOTES
# * A possible solution for the dust problem is take the top 10 offers and if the offer amount is less than X% of the
#   total available, ignore it as dust.


class MarketAnalysis(object):
    def __init__(self, config, api):
        self.open_files = {}
        self.max_age = int(config.get('BOT', 'analyseMaxAge', 30, 1, 365))
        self.currencies_to_analyse = config.get_currencies_list('analyseCurrencies')
        self.update_interval = int(config.get('BOT', 'analyseUpdateInterval', 60, 10, 3600))
        self.api = api
        self.lending_style = int(config.get('BOT', 'lendingStyle', 50, 1, 99))

        if len(self.currencies_to_analyse) != 0:
            for currency in self.currencies_to_analyse:

                try:
                    self.api.api_query("returnLoanOrders", {'currency': currency, 'limit': '5'})
                except Exception as cur_ex:
                    print "Error: You entered an incorrect currency: '" + currency + \
                          "' to analyse the market of, please check your settings. Error message: " + str(cur_ex)
                    exit(1)

                else:
                    path = "market_data/" + currency + "_market_data.csv"
                    self.open_files[currency] = path

    def run(self):
        thread = threading.Thread(target=self.run_threads)
        thread.deamon = True
        thread.start()

    def run_threads(self):
        while True:
            for cur in self.open_files:
                thread = threading.Thread(target=self.update_market_loop, args=(cur,))
                thread.deamon = False
                thread.start()
            # TODO Set this back to the config value
            time.sleep(1)

    def update_market_loop(self, cur):
        try:
            self.update_market(cur)
            self.delete_old_data(cur)
        except Exception as ex:
            ex.message = ex.message if ex.message else str(ex)
            print("Error in MarketAnalysis: {0}".format(ex.message))
            traceback.print_exc()

    def update_market(self, cur):
        with open(self.open_files[cur], 'a') as f:
            writer = csv.writer(f, lineterminator='\n')
            length = 10
            raw_data = self.api.return_loan_orders(cur, length)['offers']
            market_data = [time.time()]
            for i in xrange(length):
                market_data.extend([raw_data[i]['rate']])
                market_data.extend([raw_data[i]['amount']])
            writer.writerow(market_data)

    def delete_old_data(self, cur):
        with open(self.open_files[cur], 'rb') as file_a:
            new_a_buf = StringIO()
            writer = csv.writer(new_a_buf)
            reader2 = csv.reader(file_a)
            for row in reader2:
                if self.get_day_difference(row[0]) < self.max_age:
                    writer.writerow(row)

        # At this point, the contents (new_a_buf) exist in memory
        with open(self.open_files[cur], 'wb') as file_b:
            file_b.write(new_a_buf.getvalue())

    @staticmethod
    def get_day_difference(date_time):  # Will be in format '%Y-%m-%d %H:%M:%S'
        date1 = datetime.datetime.strptime(date_time, '%Y-%m-%d %H:%M:%S')
        now = datetime.datetime.now()
        diff_days = (now - date1).days
        return diff_days

    def get_rate_list(self, cur):
        if cur not in FULL_LIST:
            raise ValueError("{0} is not a valid currency, must be one of {1}".format(cur, FULL_LIST))
        if cur not in self.open_files:
            return []
        with open(self.open_files[cur], 'r') as f:
            reader = csv.reader(f)
            rates = []
            for row in reader:
                rates.append(row[1])
            rates = map(float, rates)
        return rates

    def get_rate_suggestion(self, cur, rates=None, method='percentile'):
        try:
            if rates is None:
                rates = self.get_rate_list(cur)
            elif cur not in self.open_files:
                return 0
            if len(rates) == 0:
                return 0
            if method == 'percentile':
                return self.get_percentile(rates, self.lending_style)
            elif method == 'golden_cross':
                raise ValueError("{0} not yet implmented")
            else:
                raise ValueError("{0} strategy not recognised")

        except Exception as ex:
            print("WARN: Exception found when analysing markets, if this happens for more than a couple minutes please "
                  "make a Github issue so we can fix it. Otherwise, you can safely ignore it. Error: " + ex.message)
            return 0

    @staticmethod
    def percentile(N, percent, key=lambda x: x):
        """
        http://stackoverflow.com/questions/2374640/how-do-i-calculate-percentiles-with-python-numpy/2753343#2753343
        Find the percentile of a list of values.

        @parameter N - is a list of values. Note N MUST BE already sorted.
        @parameter percent - a float value from 0.0 to 1.0.
        @parameter key - optional key function to compute value from each element of N.

        @return - the percentile of the values
        """
        import math
        if not N:
            return None
        k = (len(N) - 1) * percent
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return key(N[int(k)])
        d0 = key(N[int(f)]) * (c - k)
        d1 = key(N[int(c)]) * (k - f)
        return d0 + d1

    def get_percentile(self, rates, lending_style, use_numpy=use_numpy):
        if use_numpy:
            result = numpy.percentile(rates, int(lending_style))
        else:
            result = self.percentile(sorted(rates), lending_style / 100.0)
        result = truncate(result, 6)
        return result
