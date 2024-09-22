import time
import random
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, avg, broadcast
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

import os
os.environ['HADOOP_HOME'] = "/opt/homebrew/Cellar/hadoop/3.4.0/libexec"
os.environ['JAVA_HOME'] = "/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home"
# os.environ['SPARK_LOCAL_IP'] = '192.168.99.196'  # Add this line

# Common data generation function
def generate_data_batches(num_rows, batch_size=100000):
    departments = ["Engineering", "Sales", "Marketing", "HR", "Finance"]
    for i in range(0, num_rows, batch_size):
        batch = [(f"Employee_{j}", 
                  random.randint(22, 60), 
                  random.choice(departments),
                  random.randint(30000, 150000))
                 for j in range(i, min(i + batch_size, num_rows))]
        yield batch

# Number of rows in the dataset
NUM_ROWS = 10000000

print(f"Processing {NUM_ROWS} rows of data")

# PySpark Implementation
print("\n--- PySpark Implementation ---")

spark = SparkSession.builder \
    .appName("PySpark Example") \
    .config("spark.driver.memory", "4g") \
    .config("spark.executor.memory", "4g") \
    .config("spark.driver.maxResultSize", "1g") \
    .config("spark.sql.shuffle.partitions", "100") \
    .config("spark.sql.autoBroadcastJoinThreshold", "10m") \
    .config("spark.driver.extraJavaOptions", "-Xms1g") \
    .config("spark.executor.extraJavaOptions", "-Xms1g") \
    .config("spark.driver.host", "localhost") \
    .config("spark.executor.cores", "4") \
    .config("spark.executor.instances", "2") \
    .config("spark.cores.max", "8") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.memory.offHeap.enabled", "true") \
    .config("spark.memory.offHeap.size", "2g") \
    .config("spark.driver.extraClassPath", "/opt/homebrew/Cellar/apache-spark/3.4.0/libexec/jars/*") \
    .config("spark.executor.extraClassPath", "/opt/homebrew/Cellar/apache-spark/3.4.0/libexec/jars/*") \
    .master("local[*]") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

schema = StructType([
    StructField("Name", StringType(), True),
    StructField("Age", IntegerType(), True),
    StructField("Department", StringType(), True),
    StructField("Salary", IntegerType(), True)
])

pyspark_start_time = time.time()

# Process data in batches
df = None
for batch in generate_data_batches(NUM_ROWS):
    batch_df = spark.createDataFrame(batch, schema)
    if df is None:
        df = batch_df
    else:
        df = df.union(batch_df)

df = df.repartition(5, "Department")
df.cache()

result = df.groupBy("Department") \
    .agg(avg("Age").alias("Average_Age"), 
         avg("Salary").alias("Average_Salary")) \
    .orderBy(col("Average_Salary").desc())

print("Average Age and Salary by Department:")
result.show()

dept_info = spark.createDataFrame([
    ("Engineering", "Technical"),
    ("Sales", "Business"),
    ("Marketing", "Business"),
    ("HR", "Support"),
    ("Finance", "Support")
], ["Department", "Category"])

enriched_df = df.join(broadcast(dept_info), "Department")

high_paid_engineers = enriched_df.select("Name", "Age", "Salary", "Category") \
    .filter((col("Department") == "Engineering") & (col("Salary") > 100000))

print("\nHigh-paid Engineers:")
high_paid_engineers.show(5)

# Trigger actions to measure execution time
df.count()
result.count()
high_paid_engineers.count()

pyspark_end_time = time.time()
print(f"PySpark Execution time: {pyspark_end_time - pyspark_start_time:.2f} seconds")

df.unpersist()
spark.stop()

# Pandas Implementation
print("\n--- Pandas Implementation ---")

pandas_start_time = time.time()

# Process data in batches for Pandas as well
df_list = []
for batch in generate_data_batches(NUM_ROWS):
    df_list.append(pd.DataFrame(batch, columns=["Name", "Age", "Department", "Salary"]))

df = pd.concat(df_list, ignore_index=True)

result = df.groupby("Department").agg({
    "Age": "mean",
    "Salary": "mean"
}).rename(columns={
    "Age": "Average_Age",
    "Salary": "Average_Salary"
}).sort_values("Average_Salary", ascending=False)

print("Average Age and Salary by Department:")
print(result)

dept_info = pd.DataFrame([
    ("Engineering", "Technical"),
    ("Sales", "Business"),
    ("Marketing", "Business"),
    ("HR", "Support"),
    ("Finance", "Support")
], columns=["Department", "Category"])

enriched_df = df.merge(dept_info, on="Department")

high_paid_engineers = enriched_df[
    (enriched_df["Department"] == "Engineering") & 
    (enriched_df["Salary"] > 100000)
][["Name", "Age", "Salary", "Category"]]

print("\nHigh-paid Engineers (first 5 rows):")
print(high_paid_engineers.head())

pandas_end_time = time.time()
print(f"Pandas Execution time: {pandas_end_time - pandas_start_time:.2f} seconds")

# Compare execution times
print("\n--- Execution Time Comparison ---")
print(f"PySpark: {pyspark_end_time - pyspark_start_time:.2f} seconds")
print(f"Pandas:  {pandas_end_time - pandas_start_time:.2f} seconds")
