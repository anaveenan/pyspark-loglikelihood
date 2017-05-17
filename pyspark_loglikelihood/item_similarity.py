# coding: utf-8

"""
Item-item loglikilihood similarity.

Usage:
  {0} <inputFile> <outputFile> [--maxSimilaritiesPerItem=<maxSimilarItems> --maxPrefs=<maxPrefs> --threshold=<th>]
  {0} (-h | --help)
  {0} --version

Options:
  -h --help                                     Show this screen.
  --version                                     Show version.
  --maxSimilaritiesPerItem=<maxSimilarItems>    Cap the number of similar items [default: 100].
  --maxPrefs=<maxPrefs>                         Max number of preferences to consider for each user / item. [default: 500].
  --threshold=<th>                              LLR threshold [default: 0.001].
"""

import itertools

from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import desc, row_number, udf
from pyspark.sql.types import FloatType

from pyspark_loglikelihood import LOG, __version__
from pyspark_loglikelihood.loglikelihood import loglikelihood_ratio
from pyspark_loglikelihood.options import normalize_options


def _run(sc, **options):
    """Run the execution phase.

    @param sc: spark context.
    @param options: **kwargs.
    """
    input_file = options.get('inputFile', 'input.csv')
    output_file = options.get('outputFile', 'output.csv')
    threshold = float(options.get('threshold', 0.001))
    max_similarites = int(options.get('maxSimilaritiesPerItem', 100))

    LOG.info('*' * 30)

    for k, v in options.iteritems():
        LOG.info("{0}:\t{1}".format(k, v))

    LOG.info('*' * 30)

    df = sc\
        .read.text(input_file).rdd \
        .map(lambda row: row.value.split(',')) \
        .map(lambda x: (int(x[0]), int(x[1]))) \
        .distinct() \
        .persist()

    couples = df\
        .groupByKey()\
        .values()\
        .filter(lambda x: len(x) > 1)\
        .flatMap(lambda x: list(itertools.combinations(set(x), 2)))\
        .map(lambda x: (x, 1))\
        .reduceByKey(lambda x, y: x + y)\
        .map(lambda x: (x[0][0], x[0][1], x[1]))\
        .toDF(['item1', 'item2', 'bought_together'])\
        .persist()

    df2 = df\
        .toDF(['user', 'item'])\
        .groupBy("item")\
        .count()\
        .withColumnRenamed('count', 'item_count')\
        .persist()

    couples = couples\
        .join(df2, couples.item1 == df2.item)\
        .withColumnRenamed('item_count', 'bought_item1')\
        .drop('item')

    couples = couples\
        .join(df2, couples.item2 == df2.item)\
        .withColumnRenamed('item_count', 'bought_item2')\
        .drop('item')\
        .persist()

    users = df\
        .map(lambda x: int(x[0]))\
        .distinct()\
        .count()

    # item2 & not(item1)
    couples = couples.withColumn(
        'k12',
        (couples['bought_item2'] -
         couples['bought_together']))

    # item1 & not(item2)
    couples = couples.withColumn(
        'k21',
        (couples['bought_item1'] -
         couples['bought_together']))

    # not(item1) & not(item2)
    couples = couples.withColumn(
        'k22',
        users -
        (
            couples['bought_item1'] +
            couples['bought_item2'] -
            couples['bought_together']))

    # item1 & item2
    couples = couples.withColumnRenamed('bought_together', 'k11')

    # declare a udf for LLR grade and calculate
    llr = udf(loglikelihood_ratio, FloatType())
    dff = couples.withColumn('LLR', llr(couples.k11,
                                        couples.k12,
                                        couples.k21,
                                        couples.k22))

    # filter by LLR threshold
    dff = dff.filter(dff.LLR >= threshold)

    # Rank similarites by LLR grade
    ws = Window.partitionBy('item1').orderBy(desc('LLR'))
    result = dff.withColumn('Rank', row_number().over(ws))

    # cut down each group to #{max_similarites}
    result = result\
        .filter(result.Rank <= max_similarites)\
        .select(['item1', 'item2', 'LLR'])

    # Show top-100 results
    result.show(100)

    # Write result set to output destination
    result.write.csv(output_file)


if __name__ == '__main__':
    import os
    import sys
    import traceback
    from docopt import docopt

    program = os.path.basename(sys.argv[0])
    docstring = __doc__.format(program)
    options = normalize_options(docopt(docstring, version=__version__))

    exitCode = 0

    # Create a sprak context for the application
    sparkContext = SparkSession.builder \
        .appName("Item-item Loglikelihood Similarity") \
        .getOrCreate()

    try:

        # Run the calculation
        _run(sparkContext, **options)

    except Exception as e:
        LOG.error('-E- {0}'.format(traceback.format_exc()))
        exit_code = 1

    finally:

        # Stop spark context
        sparkContext.stop()

        # Exit gracefully
        sys.exit(exitCode)
