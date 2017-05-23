.. _market_analysis-section:

Market Analysis
---------------

Overview
``````````
A quick list of each config option and what they do

========================= =============================================================================================
`analyseCurrencies`_      A list of each currency you wish to record and analyse
`analyseMaxAge`_          The age (in seconds) of the oldest data you wish to keep in the DB
`analyseUpdateInterval`_  The frequency between rates requested and stored in the DB
`lendingStyle`_           The percentage used for the percentile calculation
`percentile_seconds`_     The number of seconds to analyse when working out the percentile
`MACD_long_win_seconds`_  The number of seconds to used for the long moving average
`MACD_short_win_seconds`_ The number of seconds to used for the short moving average
`keep_history_seconds`_   The age (in seconds) of the oldest data you wish to keep in the DB
`recorded_levels`_        The depth of the lending book to record in the DB, i.e. how many unfilled loans
`data_tolerance`_         The percentage of data that can be ignore as missing for the time requested in
                          ``percentile_seconds`` and ``MACD_long_win_seconds``
`daily_min_method`_       Which method (MACD or percentile) to use for the daily min calculation
`macd_multiplier`_        Only valid for MACD method. The figure to scale up the returned rate value from the MACD calculation
========================= =============================================================================================

This feature records a currency's market and allows the bot see trends. With this data, we can compute a recommended minimum lending rate per currency to avoid lending at times when the rate dips.

When this module is enabled it will start recording the lending rates for the market in an sqlite database. This will be seen in the market_data folder for your bot. This supersedes the previous method of storing it in a file. The files can be removed if you have them from older versions of the bot.

There will be a DB created for each currency you wish to record. These can be enabled in the `analyseCurrencies`_ configuration option.  

 .. warning:: The more currencies you record, the more data stored on disk and CPU processing time will be used. You will also not get as frequent results for the currencies, i.e. You may have trouble getting results for your configured ``analyseUpdateInterval`` This is explained further in the `Recording currencies`_ section. 

The module has two main methods to calculate the minimum rate:

Percentile
``````````
This method takes all the data for the given time period and works out the Xth percentile figure for that set of data, where X is the ``lendingStyle`` that you are using. For example if you are using a ``lendingStyle`` of 85 and you had a list of rates like so

  :Example: 0.04, 0.04, 0.05, 0.05, 0.05, 0.05, 0.06, 0.06, 0.06, 0.07, 0.07, 0.07, 0.08, 0.08, 0.09, 0.09, 0.09, 0.10, 0.10, 0.10

The 85th percentile would be 0.985 because 85% of rates are below this. The following configuration options should be considered when using the percentile calculation method:-
* 

MACD Moving Average Convergence Divergence
''''''''''''''''''''''''''''''''''''''''''

This method using moving averages to work out if it's a good time to lend or not. Currently this is only implemented to limit the minimum daily rate for a currency. This will be changing in the future. 
It by looking at the best rate that is available from the recorded market data for two windows, the long and short window, then taking an average of them both. If the short average is higher than the long average then it considers the market to be in a good place to lend (as the trend for rates is going up) and it will return a `suggested loan rate`_. If the long window is greater than the short window, then we will not lend as trend for rates is below what it should be.
So for example:

===== ===== ==== =========
Time  Short Long Suggested
===== ===== ==== =========
12:00 0.08  0.1  0.1
12:01 0.09  0.1  0.1
12:02 0.1   0.1  0.105
12:03 0.11  0.1  0.1155
12:04 0.12  0.1  0.126
===== ===== ==== =========

In this example, the bot would start to lend at 12:02 and it would suggest a minimum lending rate of 0.1 * `macd_multiplier`_, which by default is 1.05. Giving a rate of 0.105. This is then passed back to the main lendingbot where it will use your gaptop and gapbottom, along with spreads and all the other smarts to place loan offers.

Currently using this method gives the best results with well configured gaptop and gapbottom. This allows you to catch spikes in the market as see above. 

The short window and long window are configured by a number of seconds, the data is then taken from the DB requesting `MACD_long_win_seconds`_ * 1.1. This is to get an extra 10% of data as there is usually some lost in the recording from Poloniex.
You can also use the `data_tolerance`_ to help with the amount of data required by the bot for this calculation, that is the number of seconds that can be missing for the data to still be valid.

This current implementation is basic in it's approach, but will be built upon with time. Results seem to be good though and we would welcome your feedback if you play around with it.

suggested loan rate
~~~~~~~~~~~~~~~~~~~
If the average of the short window is greater than the average of the long window we will return the current

configuring
~~~~~~~~~~~

The number of config options and combinations for this can be quite daunting. As time goes on I hope more people will feed back useful figures for all our different configuration set ups. I have found these to work well for my particular setup:

======================= =========
Config                  Value
======================= =========
sleeptimeactive         1
sleeptimeinactive       1
spreadlend              3
gapbottom               400
gaptop                  2000
hideCoins               True
analyseCurrencies       ETH,BTC
analyseMaxAge           30
analyseUpdateInterval   60
lendingStyle            75
MACD_long_win_seconds   1800
MACD_short_win_seconds  150
percentile_seconds      1800
keep_history_seconds    1800
recorded_levels         10
data_tolerance          55
======================= =========



Recording currencies
````````````````````

All the options in this section deal with how data from poloniex is collected and stored. All the data is stored in an sqlite database, one per currency that you are recording. You can see the database files in the market_data folder of the bot.
There are a number of things to consider before configuring this section. The most important being that you can only make 6 api calls to poloniex every second. This limit includes returning your open loans, placing an loan and returning data for the live market to store in the database.

.. warning:: If you start to see the error message: ``HTTP Error 429: Too Many Requests`` then you need to review the settings in this file. In theory this shouldn't be a problem as our API limits calls to 6 per second. But it appears that it's not completely thread safe, so it can sometimes make more than 6 per second.
  If this happens, stop the bot. Increase your timer or decrease the number of recorded currencies, wait a five minutes, then start the bot again. Repeat as required.

analyseCurrencies
'''''''''''''''''

The config option ``analyseCurrencies`` is the list of currencies to record (and analyse)

None of the points below need be considered problematic unless you are planning to run with low (single digit seconds) timers on the bot. That is, the ``sleeptimeinactive``, ``sleeptimeactive`` and the ``analyseUpdateInterval``.

With that said, every currency you add to this will:

- Increase the number of db files (and therefore disk usage)
- Increase I/O and CPU usage (each currency will be writing to disk and if there's a balance, calculating the best rate)
- Reduce the number of requests you can make the API per second. This means times between stored records in the DB will be further apart and calls to place loans to Poloniex will be slower. 

configuration
~~~~~~~~~~~~~
==========  ===========================================================================================================
Format      ``CURRENCY_TICKER,STR,BTC,BTS,CLAM,DOGE,DASH,LTC,MAID,XMR,XRP,ETH,FCT,ALL,ACTIVE``
Disabling   Commenting it out will disable the entire feature.
``ACTIVE``  Entering ``ACTIVE`` analyses any currencies found in your lending account along with any other configured currencies.
``ALL``     Will analyse all coins on the lending market, whether or not you are using them.
Example     ``ACTIVE, BTC, CLAM`` will record and analyse BTC, CLAM, and any coins you are already lending.
Notes       Don't worry about duplicates when using ``ACTIVE``, they are handled internally.
==========  ===========================================================================================================

analyseMaxAge
'''''''''''''
Option ``analyseMaxAge`` is the maximum duration to store market data. Any data that is older that this number of seconds will be deleted from the DB.
This delete runs periodically, so it is possible for the there to be data older than the specified age in the database, however it won't be there for long.

configuration
~~~~~~~~~~~~~
=============  ========================================================================================================
Default value  86400
Allowed range  3600 - ?
=============  ========================================================================================================

analyseUpdateInterval
'''''''''''''''''''''

The ``analyseUpdateInterval`` is how long the bot will sleep between requests for rate data from Poloniex. Each coin has it's own thread for requests and each thread has it's own sleep.

configuration
~~~~~~~~~~~~~
=============  ========================================================================================================
Default value  10
Allowed range  1-60
=============  ========================================================================================================


lendingStyle
''''''''''''

- ``lendingStyle`` lets you choose the percentile of each currency's market to lend at.

    - Default value: 75
    - Allowed range: 1-99
    - Recommendations: Conservative = 50, Moderate = 75, Aggressive = 90, Very Aggressive = 99
    - This is a percentile, so choosing 75 would mean that your minimum will be the value that the market is above 25% of the recorded time.
    - This will stop the bot from lending during a large dip in rate, but will still allow you to take advantage of any spikes in rate.

percentile_seconds
''''''''''''''''''

``percentile_seconds`` is the number of seconds worth of data to use for the percentile calculation. This value is not used in MACD methods.

configuration
~~~~~~~~~~~~~
=============  ========================================================================================================
Default value  86400
Allowed range  300 - ``analyseMaxAge``
=============  ========================================================================================================


MACD_long_win_seconds
'''''''''''''''''''''

configuration
~~~~~~~~~~~~~
=============  ========================================================================================================
Default value  CHANGEME
Allowed range  CHANGE ME
=============  ========================================================================================================


MACD_short_win_seconds
''''''''''''''''''''''

configuration
~~~~~~~~~~~~~
=============  ========================================================================================================
Default value  CHANGEME
Allowed range  CHANGE ME
=============  ========================================================================================================


keep_history_seconds
''''''''''''''''''''

configuration
~~~~~~~~~~~~~
=============  ========================================================================================================
Default value  CHANGEME
Allowed range  CHANGE ME
=============  ========================================================================================================


recorded_levels
'''''''''''''''

configuration
~~~~~~~~~~~~~
=============  ========================================================================================================
Default value  CHANGEME
Allowed range  CHANGE ME
=============  ========================================================================================================


data_tolerance
''''''''''''''

configuration
~~~~~~~~~~~~~
=============  ========================================================================================================
Default value  CHANGEME
Allowed range  CHANGE ME
=============  ========================================================================================================


daily_min_method
''''''''''''''''

configuration
~~~~~~~~~~~~~
=============  ========================================================================================================
Default value  CHANGEME
Allowed range  CHANGE ME
=============  ========================================================================================================



macd_multiplier
'''''''''''''''

configuration
~~~~~~~~~~~~~
=============  ========================================================================================================
Default value  CHANGEME
Allowed range  CHANGE ME
=============  ========================================================================================================



