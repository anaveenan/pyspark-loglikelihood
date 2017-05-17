# coding: utf-8

"""User-user loglikilihood similarity.

Usage:
  {0} <inputFile> <outputFile> [--numOfNeighbors=<numOfNeighbors> --numOfRecommednations=<numOfRecommednations>]
  {0} (-h | --help)
  {0} --version

Options:
  -h --help                                       Show this screen.
  --version                                       Show version.
  --numOfNeighbors=<numOfNeighbors>               N-neighborhood size [default: 24].
  --numOfRecommednations=<numOfRecommednations>   Number of recommendations pers user. [default: 100].
"""

from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import desc, row_number, udf
from pyspark.sql.types import FloatType, IntegerType, StructField, StructType

from pyspark_loglikelihood import LOG, __version__
from pyspark_loglikelihood.loglikelihood import loglikelihood_ratio
from pyspark_loglikelihood.options import normalize_options


def _run(sc, **options):
    """Run the execution phase.

    @param sc: spark context.
    @param options: **kwargs.
    """
    LOG.info('*' * 30)
    for k, v in options.iteritems():
        LOG.info("{0}:\t{1}".format(k, v))
    LOG.info('*' * 30)

    input_file = options.get('inputFile', 'input.csv')
    output_file = options.get('outputFile', 'output.csv')
    num_of_neighbors = options.get('numOfNeighbors', 24)
    num_of_recommednations = options.get('numOfRecommednations', 100)

    # Read dataset
    schema = StructType([
        StructField("user", IntegerType()),
        StructField("item", IntegerType()),
    ])

    df = sc\
        .read.csv(input_file, header=False, schema=schema)\
        .distinct()

    # Drop down users with less than 2 purchases
    df = df.join(df.groupBy('item').count(), on='item')

    df = df\
        .filter(df['count'] > 1)\
        .select(['user', 'item'])\
        .persist()

    # Map User -> #{Purchases}
    purchases = df\
        .groupBy("user")\
        .count()\
        .withColumnRenamed("count", "purchases")

    # Count total number of items
    num_items = df\
        .select('item')\
        .distinct()\
        .count()

    # Generate couples
    couples = df\
        .join(df.withColumnRenamed("user", "user2"), on='item')\
        .withColumnRenamed("user", "user1")

    # Count `intersection` per couple
    couples = couples\
        .filter(couples.user1 != couples.user2)\
        .groupBy(["user1", "user2"])\
        .count()\
        .withColumnRenamed("count", "intersection")

    # Count total purchases per each user
    couples = couples\
        .join(purchases, couples.user1 == purchases.user)\
        .withColumnRenamed('purchases', 'bought_user1')\
        .drop('user')

    couples = couples\
        .join(purchases, couples.user2 == purchases.user)\
        .withColumnRenamed('purchases', 'bought_user2')\
        .drop('user')

    # Prepare K11, k12, k21, k22 matrix for each couple
    couples = couples.withColumn(
        'k12',
        (couples['bought_user2'] -
         couples['intersection']))

    couples = couples.withColumn(
        'k21',
        (couples['bought_user1'] -
         couples['intersection']))

    couples = couples.withColumn(
        'k22',
        num_items -
        (
            couples['bought_user1'] +
            couples['bought_user2'] -
            couples['intersection']))

    couples = couples\
        .withColumnRenamed('intersection', 'k11')\
        .drop('bought_user1')\
        .drop('bought_user2')

    # Create a UDF for LLR grades and assign to each couple
    llr = udf(loglikelihood_ratio, FloatType())
    df1 = couples.withColumn('LLR', llr(couples.k11,
                                        couples.k12,
                                        couples.k21,
                                        couples.k22))

    # Build a N-neighborhood for each user ( # = num_of_neighbors )
    ws = Window.partitionBy('user1').orderBy(desc('LLR'))
    df1 = df1.withColumn('Rank', row_number().over(ws))

    df1 = df1\
        .filter(df1.Rank <= num_of_neighbors)\
        .select(['user1', 'user2', 'LLR'])

    df1 = df1\
        .join(df, df1.user2 == df.user)\
        .drop('user')\
        .persist()

    # Now we have a "neighborhood" for each user.
    # Let's sort the items bought by the neighbors
    # by the LLR score of each neighbor.
    df1 = df1\
        .groupBy(['user1', 'item'])\
        .sum('LLR')\
        .withColumnRenamed('sum(LLR)', 'LLR_agg')

    # Build a set of recommendations for each user
    result = df1\
        .select(['user1', 'item'])\
        .subtract(df)\
        .join(df1, ['user1', 'item'])\
        .withColumnRenamed('user1', 'user')\
        .persist()

    # Cut down recommendations set to #{numOfRecommednations}
    ws = Window.partitionBy('user').orderBy(desc('LLR_agg'))
    result = result.withColumn('Rank', row_number().over(ws))

    result = result\
        .filter(result.Rank <= num_of_recommednations)\
        .select(['user', 'item', 'LLR_agg'])

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
        .appName("User-user Loglikelihood Similarity") \
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
