import os
import sys
import threading
import time
import traceback
import datetime
import pandas as pd
import sqlite3 as lite
from sqlite3 import Error

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
# [ ] Reduce the time in the config file to allow 1 sec
# [x] Record more data (we can work out what to do with it later)
# [ ] Provide something that takes into account dust offers. (The golden cross works well on BTC, not slower markets)
# [ ] RE: above. Weighted rate.
# [ ] Add docstring to everything
# [ ] Unit tests

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
        self.recorded_levels = 10
        self.modules_dir = os.path.dirname(os.path.realpath(__file__))
        self.top_dir = os.path.dirname(self.modules_dir)
        self.db_dir = os.path.join(self.top_dir, 'market_data')
        self.MACD_long_win_seconds = int(config.get('MarketAnalysis', 'MACD_long_win_seconds', 1800, 60))
        self.MACD_short_win_seconds = int(config.get('MarketAnalysis', 'MACD_short_win_seconds', 150, 1))
        self.percentile_seconds = int(config.get('MarketAnalysis', 'percentile_seconds', 150, 1))
        self.keep_history_seconds = int(config.get('MarketAnalysis', 'keep_history_seconds', 150, 1))

        if len(self.currencies_to_analyse) != 0:
            for currency in self.currencies_to_analyse:
                try:
                    self.api.api_query("returnLoanOrders", {'currency': currency, 'limit': '5'})
                except Exception as cur_ex:
                    print "Error: You entered an incorrect currency: '" + currency + \
                          "' to analyse the market of, please check your settings. Error message: " + str(cur_ex)
                    exit(1)

    def run(self):
        for cur in self.currencies_to_analyse:
            db_con = self.create_connection(cur)
            self.create_rate_table(db_con, self.recorded_levels)
            db_con.close()
        self.run_threads()

    def run_threads(self):
        for cur in self.currencies_to_analyse:
            thread = threading.Thread(target=self.update_market_thread, args=(cur,))
            thread.deamon = True
            thread.start()

    def run_del_threads(self):
        while True:
            for cur in self.currencies_to_analyse:
                del_thread = threading.Thread(target=self.delete_old_data_thread, args=(cur,))
                del_thread.daemon = True
                del_thread.start()
            # TODO set a reasonable default and allow config
            time.sleep(30)

    def update_market_thread(self, cur):
        try:
            db_con = self.create_connection(cur)
            self.update_market(db_con, cur, self.recorded_levels)
        except Exception as ex:
            ex.message = ex.message if ex.message else str(ex)
            print("Error in MarketAnalysis: {0}".format(ex.message))
            traceback.print_exc()

    def delete_old_data_thread(self, cur, seconds):
        while True:
            try:
                db_con = self.create_connection(cur)
                self.delete_old_data(db_con, seconds)
            except Exception as ex:
                ex.message = ex.message if ex.message else str(ex)
                print("Error in MarketAnalysis: {0}".format(ex.message))
                traceback.print_exc()

    def update_market(self, db_con, cur, levels):
        while True:
            raw_data = self.api.return_loan_orders(cur, levels)['offers']
            market_data = []
            for i in xrange(levels):
                market_data.append(str(raw_data[i]['rate']))
                market_data.append(str(raw_data[i]['amount']))
            market_data.append('0')
            insert_sql = "INSERT INTO loans ("
            for level in xrange(levels):
                insert_sql += "rate{0}, ".format(level)
                insert_sql += "amnt{0}, ".format(level)
            insert_sql += "percentile"
            insert_sql += ") VALUES ({0});".format(','.join(market_data))
            with db_con:
                db_con.execute(insert_sql)

    def delete_old_data(self, db_con, seconds):
        """
        Delete old data from the database

        :param db_con: Connection to the database
        :param cur: The currency (table) to remove data from
        :param seconds: The time in seconds of the oldest data to be kept
        """
        del_time = int(time.time()) - seconds
        with db_con:
            query = "DELETE FROM loans WHERE unixtime < {0};".format(del_time)
            cursor = db_con.cursor()
            cursor.execute(query)

    @staticmethod
    def get_day_difference(date_time):  # Will be a number of seconds since epoch
        date1 = datetime.datetime.fromtimestamp(float(date_time))
        now = datetime.datetime.now()
        diff_days = (now - date1).days
        return diff_days

    def get_rate_list(self, cur, seconds):
        # Request more data from the DB than we need to allow for skipped seconds
        request_seconds = int(seconds * 1.1)
        if cur not in FULL_LIST:
            raise ValueError("{0} is not a valid currency, must be one of {1}".format(cur, FULL_LIST))
        if cur not in self.currencies_to_analyse:
            return []
        db_con = self.create_connection(cur)
        # TODO Remove hardcoded values
        price_levels = ['rate0']
        rates = self.get_rates_from_db(db_con, from_date=time.time() - request_seconds, price_levels=price_levels)
        df = pd.DataFrame(rates)
        columns = ['time']
        columns.extend(price_levels)
        df.columns = columns
        # convert unixtimes to datetimes so we can resample
        df.time = pd.to_datetime(df.time, unit='s')
        # If we don't have enough data return df, otherwise the resample will fill out all values with the same data
        if len(df) < seconds:
            return df
        # Resample into 1 second intervals, average if we get two in the same second and fill any empty spaces with the
        # previous value
        df = df.resample('1s', on='time').mean().ffill()
        return df

    def get_rate_suggestion(self, cur, rates=None, method='golden_cross'):
        if method == 'percentile':
            seconds = self.percentile_seconds
        elif method == 'golden_cross':
            seconds = self.MACD_long_win_seconds
        else:
            print("Error: {0} method not recognised, falling back to percentile")
            method == 'percentile'
            seconds = self.percentile_seconds

        try:
            if rates is None:
                rates = self.get_rate_list(cur, seconds)
            elif cur not in self.open_files:
                return 0
            if len(rates) == 0:
                return 0
            if method == 'percentile':
                # rates is a tuple with the first entry being unixtime
                rates = [x[1] for x in rates]
                return self.get_percentile(rates, self.lending_style)
            elif method == 'golden_cross':
                seconds = self.MACD_long_win_seconds
                if len(rates) < seconds:
                    print(" : Need more data for analysis, still collecting. I have {0}/{1} records"
                          .format(len(rates), seconds))
                    return 0
                rate = truncate(self.get_golden_cross_rate(cur, rates, self.MACD_long_win_seconds,
                                                           self.MACD_short_win_seconds), 6)
                print("Cur: {0}, Golden : {1}, Percent {2}, Best: {3}"
                      .format(cur, rate, self.get_percentile(rates, self.lending_style), rates.rate0.iloc[-1]))
                return rate

        except Exception as ex:
            print("WARN: Exception found when analysing markets, if this happens for more than a couple minutes please "
                  "make a Github issue so we can fix it. Otherwise, you can safely ignore it. Error:"
                  "{0}".format(ex.message))
            return 0

    @staticmethod
    def percentile(N, percent, key=lambda x: x):
        """
        http://stackoverflow.com/questions/2374640/how-do-i-calculate-percentiles-with-python-numpy/2753343#2753343
        Find the percentile of a list of values.

        :parameter N: A list of values. Note N MUST BE already sorted.
        :parameter percent: A float value from 0.0 to 1.0.
        :parameter key: Optional key function to compute value from each element of N.

        :return: Percentile of the values
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

    def get_golden_cross_rate(self, cur, rates_df, short_period=150, long_period=1800):
        short_rate = rates_df.rate0.tail(short_period).mean()
        long_rate = rates_df.rate0.tail(long_period).mean()
        # TODO remove the sys writes
        if short_rate > long_rate:
            sys.stdout.write("Short higher : ")
            rate = short_rate if rates_df.rate0.iloc[-1] < short_rate else rates_df.rate0.iloc[-1]
        else:
            sys.stdout.write("Long  higher : ")
            rate = long_rate
        # TODO Needs config option
        rate = rate * 1.05
        return rate

    def create_connection(self, cur, db_dir=None, db_type='sqlite3'):
        """
        Create a connection to the sqlite DB. This will create a new file if one doesn't exist.  We can use :memory:
        here for db_path if we don't want to store the data on disk

        :param cur: The currency (table) in the DB
        :param db_path: DB directory
        :return: Connection object or None
        """
        if db_dir is None:
            db_path = os.path.join(self.db_dir, '{0}.db'.format(cur))
        try:
            con = lite.connect(db_path)
            return con
        except Error as ex:
            print(ex.message)

        return None

    def create_rate_table(self, db_con, levels):
        """
        Create a new table to hold rate data.

        :param db_con: Connection to the database
        :param cur: The currency being stored in the DB. There's a table for each currency.
        :param levels: The depth of offered rates to store
        """
        with db_con:
            cursor = db_con.cursor()
            create_table_sql = "CREATE TABLE IF NOT EXISTS loans (id INTEGER PRIMARY KEY AUTOINCREMENT," + \
                               "unixtime integer(4) not null default (strftime('%s','now')),"
            for level in xrange(levels):
                create_table_sql += "rate{0} FLOAT, ".format(level)
                create_table_sql += "amnt{0} FLOAT, ".format(level)
            create_table_sql += "percentile FLOAT);"
            cursor.execute("PRAGMA journal_mode=wal")
            cursor.execute(create_table_sql)

    def get_rates_from_db(self, db_con, from_date=None, to_date=None, price_levels=['rate0']):
        """
        Query the DB for all rates for a particular currency

        :param db_con: Connection to the database
        :param cur: The currency you want to get the rates for
        :param from_date: The earliest data you want, specified in unix time (seconds since epoch)
        :param to_date: The latest data you want, specified in unix time (seconds since epoch)
        #TODO Change NEEDVARIABLE below
        :price_level: We record multiple price levels in the DB, the best offer being rate0, up to whateve you have
        configure NEEDVARIABLE to. You can also ask for VWR, which is a special volume weight rate designed to skip
        'dust' offers
        """
        with db_con:
            cursor = db_con.cursor()
            query = "SELECT unixtime, {0} FROM loans ".format(",".join(price_levels))
            if from_date is not None and to_date is not None:
                query += "WHERE unixtime > {0} AND unixtime < {1}".format(from_date, to_date)
            if from_date is not None:
                query += "WHERE unixtime > {0}".format(from_date)
            if to_date is not None:
                query += "WHERE unixtime < {0}".format(to_date)
            query += ";"
            cursor.execute(query)
            return cursor.fetchall()
