import os
import uuid
import boto3
import pandas as pd
from io import BytesIO
from datetime import datetime

s3 = boto3.client('s3')

# Environment variables
SOURCE_BUCKET = os.environ['SOURCE_BUCKET']
SOURCE_PREFIX = os.environ['SOURCE_PREFIX']
TARGET_BUCKET = os.environ['TARGET_BUCKET']
TARGET_PREFIX = os.environ['TARGET_PREFIX']
METADATA_PREFIX = os.environ.get('METADATA_PREFIX', 'metadata')

FILTER_YEAR = '2025'
FILTER_MONTH = '08'


SELECTED_TABLES = ['communicationssent']
BATCH_SIZE = 10

#  List source files — choose YEAR or MONTH mode
def list_source_files(table_name):
    #  Uncomment this line to process WHOLE YEAR
    #prefix = f"{SOURCE_PREFIX}{table_name}/year={FILTER_YEAR}/"

    #  Uncomment this line instead to process SPECIFIC MONTH
    prefix = f"{SOURCE_PREFIX}{table_name}/year={FILTER_YEAR}/month={FILTER_MONTH}/"

    paginator = s3.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=SOURCE_BUCKET, Prefix=prefix)
    files = []
    for page in page_iterator:
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('.parquet'):
                files.append(key)
    return files

#  Read Parquet from S3
def read_parquet_from_s3(bucket, key):
    obj = s3.get_object(Bucket=bucket, Key=key)
    return pd.read_parquet(BytesIO(obj['Body'].read()))

#  Write daily Parquet to S3
def write_parquet_to_s3(df, table_name, date):
    try:
        year = date.year
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"
        unique_id = uuid.uuid4().hex[:8]
        target_key = f"{TARGET_PREFIX}{table_name}/year={year}/month={month}/day={day}/data_{date}_{unique_id}.parquet"
        buffer = BytesIO()
        df.to_parquet(buffer, index=False)
        buffer.seek(0)
        s3.put_object(Bucket=TARGET_BUCKET, Key=target_key, Body=buffer.getvalue())
        print(f" Written: {target_key} with {len(df)} records")
        return True
    except Exception as e:
        print(f" Failed to write Parquet for {table_name} on {date}: {e}")
        return False

#  List written files — choose YEAR or MONTH mode
def list_written_files(table_name):
    # Uncomment this line to read WHOLE YEAR output
    #prefix = f"{TARGET_PREFIX}{table_name}/year={FILTER_YEAR}/"

    #  Uncomment this line instead to read SPECIFIC MONTH output
    prefix = f"{TARGET_PREFIX}{table_name}/year={FILTER_YEAR}/month={FILTER_MONTH}/"

    paginator = s3.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=TARGET_BUCKET, Prefix=prefix)
    files = []
    for page in page_iterator:
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('.parquet'):
                files.append(key)
    return files

#  Generate and write metadata CSV
def write_metadata_from_s3(table_name):
    files = list_written_files(table_name)
    metadata = []

    for key in files:
        try:
            df = read_parquet_from_s3(TARGET_BUCKET, key)
            if 'createdatetime' not in df.columns:
                continue
            df['createdatetime'] = pd.to_datetime(df['createdatetime'], errors='coerce')
            df = df[df['createdatetime'].notnull()]
            df['date'] = df['createdatetime'].dt.date
            for date, group in df.groupby('date'):
                metadata.append({
                    'table_name': table_name,
                    'date': str(date),
                    'record_count': len(group)
                })
        except Exception as e:
            print(f" Error reading back file {key}: {e}")

    if metadata:
        meta_df = pd.DataFrame(metadata)
        aggregated_df = meta_df.groupby(['table_name', 'date'], as_index=False).agg({'record_count': 'sum'})
        for table in aggregated_df['table_name'].unique():
            table_meta = aggregated_df[aggregated_df['table_name'] == table]
            summary_row = pd.DataFrame([{
                'table_name': table,
                'date': 'SUMMARY',
                'record_count': table_meta['record_count'].sum()
            }])
            final_df = pd.concat([table_meta, summary_row], ignore_index=True)

            # Filename includes year, month (optional), and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            source_date_str = f"{FILTER_YEAR}_{FILTER_MONTH}_{timestamp}"  # Month included
            #source_date_str = f"{FILTER_YEAR}_{timestamp}"  # Use this for year-only mode

            buffer = BytesIO()
            final_df.to_csv(buffer, index=False)
            buffer.seek(0)

            meta_key = f"{METADATA_PREFIX}{table}/metadata_{source_date_str}.csv"
            s3.put_object(Bucket=TARGET_BUCKET, Key=meta_key, Body=buffer.getvalue())
            print(f" Metadata written: {meta_key}")

#  Lambda entry point
def lambda_handler(event, context):
    for table_name in SELECTED_TABLES:
        files = list_source_files(table_name)
        daily_data = {}

        for i in range(0, len(files), BATCH_SIZE):
            batch_files = files[i:i + BATCH_SIZE]
            for file_key in batch_files:
                try:
                    df = read_parquet_from_s3(SOURCE_BUCKET, file_key)
                    if 'createdatetime' not in df.columns:
                        continue
                    df['createdatetime'] = pd.to_datetime(df['createdatetime'], errors='coerce')
                    invalid_rows = df[df['createdatetime'].isnull()]
                    if not invalid_rows.empty:
                        print(f" {len(invalid_rows)} rows dropped due to invalid createdatetime in file {file_key}")
                    df = df[df['createdatetime'].notnull()]
                    df['date'] = df['createdatetime'].dt.date
                    for date, group in df.groupby('date'):
                        if date not in daily_data:
                            daily_data[date] = []
                        daily_data[date].append(group.drop(columns=['date']))
                except Exception as e:
                    print(f" Error processing file {file_key}: {e}")

        for date, groups in daily_data.items():
            full_df = pd.concat(groups, ignore_index=True)
            full_df.drop_duplicates(inplace=True)
            full_df['createdatetime'] = full_df['createdatetime'].astype('datetime64[ms]')
            write_parquet_to_s3(full_df, table_name, date)

        write_metadata_from_s3(table_name)

    return {'status': 'success'}
