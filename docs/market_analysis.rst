.. _market_analysis-section:

Market Analysis
---------------

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

- MACD Moving Average Convergence Divergence
  This method using moving averages to work out if it's a good time to lend or not. Currently this is only implemented to limit the minimum daily rate for a currency. This will be changing in the future. 
  It works by recording the 

- Percentile
  This method uses two configuration options. 
  - ``analyseMaxAge`` #TODO - Change this option.
  This option is the max age in seconds of results to use.

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


- ``analyseMaxAge`` is the maximum duration to store market data.

    - Default value: 30 days
    - Allowed range: 1-365 days

- ``analyseUpdateInterval`` is how often (asynchronous to the bot) to record each market's data.

     - Default value: 60 seconds
     - Allowed range: 10-3600 seconds

 .. note:: Storage usage caused by the above two settings can be calculated by: ``<amountOfCurrencies> * 30 * analyseMaxAge * (86,400 / analyseUpdateInterval)`` bytes. Default settings with ``ALL`` currencies enabled will result in using ``15.552 MegaBytes`` maximum.

- ``lendingStyle`` lets you choose the percentile of each currency's market to lend at.

    - Default value: 75
    - Allowed range: 1-99
    - Recommendations: Conservative = 50, Moderate = 75, Aggressive = 90, Very Aggressive = 99
    - This is a percentile, so choosing 75 would mean that your minimum will be the value that the market is above 25% of the recorded time.
    - This will stop the bot from lending during a large dip in rate, but will still allow you to take advantage of any spikes in rate.



Overview
``````````
A quick list of each config option and what they do

====================== ================================================================================================
**[MarketAnalysis] Config section**
-----------------------------------------------------------------------------------------------------------------------
analyseCurrencies      A list of each currency you wish to record and analyse
analyseMaxAge          The age (in seconds) of the oldest data you wish to keep in the DB
analyseUpdateInterval  The frequency between rates requested and stored in the DB
lendingStyle           The percentage used for the percentile calculation
percentile_seconds     The number of seconds to analyse when working out the percentile
MACD_long_win_seconds  The number of seconds to used for the long moving average
MACD_short_win_seconds The number of seconds to used for the short moving average
keep_history_seconds   The age (in seconds) of the oldest data you wish to keep in the DB
recorded_levels        The depth of the lending book to record in the DB, i.e. how many unfilled loans
data_tolerance         The percentage of data that can be ignore as missing for the time requested in
                       ``percentile_seconds`` and ``MACD_long_win_seconds``
====================== ================================================================================================

====================== ================================================================================================
**[Daily_min] Config section**
-----------------------------------------------------------------------------------------------------------------------
method                 Which method (MACD or percentile) to use for the daily min calculation
multiplier             Only valid for MACD method. The figure to scale up the returned rate value from the MACD calculation
====================== ================================================================================================

