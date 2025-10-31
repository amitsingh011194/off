import json
import boto3
import psycopg2
import os
import io
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
from datetime import datetime
import pytz
import logging
import gc
from psycopg2 import OperationalError, ProgrammingError
from config import (
    upload_parquet_to_s3, save_config_to_s3, load_config,load_config_from_ssm,
    fix_datetime_columns, fill_nulls_for_tables, upload_summary_csv_to_s3, get_db_credentials
)

s3 = boto3.client('s3')
 
# Load all ENV variables
CONFIG_ENV = load_config_from_ssm()
 
config_key = CONFIG_ENV.get('config_key')
json_config_s3_key = CONFIG_ENV.get('json_config_s3_key')
region_name = CONFIG_ENV.get('region_name')
s3_bucket_name = CONFIG_ENV.get('s3_bucket_name')
summary_csv_s3_prefix = CONFIG_ENV.get('summary_csv_s3_prefix')
target_path = CONFIG_ENV.get('target_path')
secret_name = CONFIG_ENV.get('secret_name')

#hardcode a path here to contain the removable column list
key = ""

current_date = datetime.now().strftime("%Y-%m-%d")

# Fetch credentials from Secrets Manager
db_credentials = get_db_credentials()

db_host = db_credentials['host']
db_name = db_credentials['dbname']
db_user = db_credentials['username']
db_password = db_credentials['password']
db_port = db_credentials['port']

#  Set static end_date as requested
end_date = datetime.strptime('2025-09-17', "%Y-%m-%d")


#columns to be removed
try:
    response = s3.get_object(Bucket=s3_bucket_name, Key=key)
    content = response['Body'].read().decode('utf-8')
    removecolumns = json.loads(content)
    logger.info(f"Columns to remove: {removecolumns}")
except Exception as e:
    logger.error(f"Error reading remove_columns.json from S3: {str(e)}")
    removecolumns = []

# Logging setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    config = load_config()
    chunk_size = 1000
    summary_data = []

    try:
        for table in config:
            try:
                conn = psycopg2.connect(
                    host=db_host, database=db_name, user=db_user,
                    password=db_password, port=db_port
                )
                cursor = conn.cursor()
                logger.info(f" New DB connection established for table: {table.get('TableName')}")

                if table.get('IsActive') == 'y':
                    table_name = table.get('TableName')
                    query = table.get('SqlStatement')
                    where_clause = table.get('WhereClause')
                    logger.info(f"where clause flag for {table_name} is {where_clause}")

                    #  Use LastRunDate from config as start_date
                    start_date = datetime.strptime(table.get('LastRunDate'), "%Y-%m-%d")

                    if where_clause == 'y':
                        incremental_column = table.get('IncrementalColumn')
                        if incremental_column and incremental_column.strip():
                            #  Add IS NOT NULL to avoid null records
                            date_filter = (
                                f"{incremental_column} BETWEEN '{start_date.strftime('%Y-%m-%d')} 00:00:00' "
                                f"AND '{end_date.strftime('%Y-%m-%d')} 23:59:59' AND {incremental_column} IS NOT NULL"
                            )

                            if "WHERE" in query.upper():
                                query += f" AND {date_filter}"
                            else:
                                query += f" WHERE {date_filter}"

                            #  Log final query for debugging
                            logger.info(f"Final query for {table_name}: {query}")
                        else:
                            logger.warning(f" Skipping date filter for table {table_name} due to missing IncrementalColumn.")

                    logger.info(f"query execution is started: {query}")
                    cursor.execute(query)
                    
                    if table.get('IsIncrementalLoad') != 'y':
                        table['IsActive'] = 'n'
                    
                    colnames_all = [desc[0] for desc in cursor.description]
                    
                    colnames = [col for col in colnames_all if col not in removecolumns]
                    


                    chunk_number = 1
                    total_rows = 0

                    while True:
                        rows = cursor.fetchmany(chunk_size)
                        if not rows:
                            logger.info(f"No data found for table {table_name}. Uploading empty Parquet file.")
                            summary_data.append({
                                'TableName': table_name,
                                'ChunksCreated': 0,
                                'TotalRecords': 0,
                                'ProcessedDate': current_date
                            })
                            #  Update LastRunDate to end_date
                            table['LastRunDate'] = end_date.strftime("%Y-%m-%d")
                            break

                        df = pd.DataFrame(rows, columns=colnames)
                        logger.info(f"Chunk {chunk_number} of table {table_name} has {len(df)} rows.")
                        total_rows += len(df)

                        df = fix_datetime_columns(df)
                        df = fill_nulls_for_tables(df)

                        buffer = io.BytesIO()
                        writer = None
                        batch_size = 1000

                        for start in range(0, len(df), batch_size):
                            batch_df = df.iloc[start:start + batch_size]
                            batch_table = pa.Table.from_pandas(batch_df, preserve_index=False)

                            if writer is None:
                                writer = pq.ParquetWriter(buffer, batch_table.schema)

                            writer.write_table(batch_table)
                            del batch_df, batch_table
                            gc.collect()

                        if writer:
                            writer.close()

                        timezone = pytz.timezone("Asia/Kolkata")
                        year = start_date.strftime("%Y")
                        month = start_date.strftime("%m")
                        day = start_date.strftime("%d")
                        s3_path = f"{target_path}{table_name}/year={year}/month={month}/day={day}/data_chunk{chunk_number}_{start_date.date()}.parquet"

                        s3.put_object(Bucket=s3_bucket_name, Key=s3_path, Body=buffer.getvalue())
                        logger.info(f"Uploaded chunk {chunk_number} of table {table_name} to {s3_path}")
                        chunk_number += 1

                        del df, writer, buffer
                        gc.collect()

                    logger.info(f"Total rows processed for table {table_name}: {total_rows}")
                    #  Update LastRunDate to end_date
                    table['LastRunDate'] = end_date.strftime("%Y-%m-%d")

                    summary_data.append({
                        'TableName': table_name,
                        'ChunksCreated': chunk_number - 1,
                        'TotalRecords': total_rows,
                        'ProcessedDate': current_date
                    })

                try:
                    cursor.close()
                    conn.close()
                    logger.info(f" Closed DB connection for table: {table.get('TableName')}")
                except Exception as close_err:
                    logger.info(f" Error closing DB connection for table {table.get('TableName')}: {close_err}")

            except ProgrammingError as pe:
                logger.info(f"Query error in table {table.get('TableName')}: {pe}")
            except Exception as e:
                logger.info(f"Unexpected error while processing table {table.get('TableName')}: {e}")

        logger.info(f"loading metadata for {len(summary_data)} tables")
        upload_summary_csv_to_s3(summary_data, s3_bucket_name, summary_csv_s3_prefix, start_date, end_date)

    except OperationalError as oe:
        logger.info(f"Database connection failed: {oe}")
    except Exception as e:
        logger.info(f"Unexpected error in Lambda handler: {e}")

    finally:
        save_config_to_s3(config, s3_bucket_name, json_config_s3_key)

    return {
        'statusCode': 200,
        'body': 'Success!'
    }



{
  "TENANT_ID": "${TENANT_ID}",
  "ENV_ID": "${ENV_ID}",
  "CUSTOMER_ID": "${CUSTOMER_ID}"
}


/saas-platform/psprod1/3a5c0629/lambdareadonlyreadrepl/json_config_s3_key
