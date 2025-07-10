import ast
import awswrangler as wr
import boto3
import csv
import datetime
import logging
import os
import pandas as pd

from aws_xray_sdk.core import patch_all
from config import (
    col_dict,
    rename_db_field_dict,
    function_step_alert,
)

patch_all()

source_s3_bucket = os.environ['source_s3_bucket']
combined_s3_bucket = os.environ['combined_s3_bucket']
hour_diff = int(os.environ['hour_diff'])
source_prefix = os.environ['source_prefix']
file_format = os.environ['file_format']
daily_files_list = set(os.environ['daily_files_list'].split(" "))
monthly_files_list = set(os.environ['monthly_files_list'].split(" "))
combined_account_prefix = os.environ['combined_account_prefix']
combined_account_file_prefix = os.environ['combined_account_file_prefix']
combined_payment_file_prefix = os.environ['combined_payment_file_prefix']
combined_payment_kill_prefix = os.environ['combined_payment_kill_prefix']
combined_killfile_prefix = os.environ['combined_kill_file_prefix']
processed_s3_bucket = os.environ['processed_s3_bucket']
processed_prefix = os.environ['processed_prefix']

log_level = os.environ.get('log_level','INFO')
logger = logging.getLogger()
logger.setLevel(log_level)

# Connecting to aws sevices
s3 = boto3.resource('s3')
s3_client = boto3.client('s3')

source_s3bucket = s3.Bucket(source_s3_bucket)
combined_s3bucket = s3.Bucket(combined_s3_bucket)


def lambda_handler(event, context):
    t = datetime.datetime.today()
    t = t - datetime.timedelta(hours=hour_diff)
    d = t.strftime('%Y%m%d')
    time_now = t.strftime('%H%M%S')

    filename_bucket = []
    full_filename = []
    full_filename_key = []

    try:
        for obj in source_s3bucket.objects.filter(
                Prefix = source_prefix ):
            split_file_key = obj.key
            file_name = os.path.basename(split_file_key)
            if split_file_key.endswith('/'):
                continue

            if obj.size > 0:
                split_file_key = obj.key
                file_name = os.path.basename(split_file_key)
                file_name_parts = file_name.split('_')
                first_name = file_name_parts[0]
                file_date = file_name_parts[1]
                file_type = file_name_parts[2].split('.')[-1]
                logger.info("Splited file name for validation. (Name - Date - file format)")

                if file_type.lower() != file_format:
                    message = "Wrong file type"
                    logger.info(message)
                    function_step_alert(message)
                    return 
                
                else:
                    if file_date == d:
                        filename_bucket.append(first_name.lower())
                        full_filename.append(file_name)
                        full_filename_key.append(split_file_key)                        
                        logger.info(f"Appened {first_name} file to its respective lists")
                    elif len(file_name_parts) == 3:
                        message = f"{file_name} does not match today's date/dateformat"
                        logger.info(message)
                        function_step_alert(message)
                        return
                    else:
                        message = "Split error: Name contains more than expected '_'"
                        logger.info(message)
                        function_step_alert(message)
                        return
                    
            else:
                message = f"The file {file_name} is empty."
                logger.info(message)
                function_step_alert(message)
                return          
            
    except Exception as e:
        message = "Split error: Name contains more than expected '_'"
        logger.exception(message)
        function_step_alert(message)
        return
 
    logger.info("All file names are identified and appended into respective lists")
    logger.info(f"count of files recieved:{len(filename_bucket)},files received:{filename_bucket}")

    set_filename_bucket = frozenset(filename_bucket)
    set_dailyfiles = frozenset(daily_files_list)
    set_monthlyfiles = frozenset(monthly_files_list)

    valid_sets = [
        set_dailyfiles,
        set_monthlyfiles,
        set_monthlyfiles | set_dailyfiles
    ]

    logger.info("Obtained filename list from environment variable for comparison")

    if set_filename_bucket not in valid_sets:
        message = "Bucket contains different files."
        logger.info(message)
        function_step_alert(message)
        return
    
    logger.info("proceding to schema validation")
    
    files_processed = 0
    df_dict = {}
    for folder_filename in full_filename_key:
        s3_object = s3.Object(source_s3_bucket, folder_filename)
        full_file_name_key = os.path.basename(folder_filename)
        file_name_key = full_file_name_key.split('_')[0].lower()
        file_data = s3_object.get()['Body'].read().decode('utf-8-sig').splitlines()
        logger.info("Obtained file content from s3")
        lines = csv.reader(file_data)
        headers = next(lines)
        headers = [header.lower() for header in headers]

        try:
            if file_name_key in col_dict:
                files_processed += 1
                if ((set(headers) != set(
                        col_dict[file_name_key].split(" "))) | (
                        len(headers) != len(
                        col_dict[file_name_key].split(" ")))):
                    message = f"{file_name_key} schema not valid"
                    logger.info(message)
                    function_step_alert(message)
                    return
                else:
                    df = wr.s3.read_csv(f"s3://{source_s3_bucket}/{folder_filename}",dtype=object)
                    df_dict[file_name_key] = df
                    logger.info(f"{file_name_key} schema is correct")
                
        except Exception as e:
            message = f"Error Encountered:{e}"
            logger.exception(message)
            function_step_alert(message)
            return
        
    logger.info("All file schemas are correct")            
    
    logger.info(f"{files_processed} files are processed")
    
    ################Map client columns to Collassist namespace#######################
    for key in filename_bucket:
        df = df_dict[key]
        df.columns = df.columns.str.lower()
        df.rename(columns=rename_db_field_dict.get(key, {}), inplace=True)
        logger.info(f"Changed all column names of {key} to db column names")
        logger.info(df.columns)
        if key == 'scetoexlaccount':
            wr.s3.to_csv(df=df,
                            path=f"s3://{combined_s3_bucket}/{combined_account_prefix}/{combined_account_file_prefix}_{d}_{time_now}.csv")
        elif key == 'scetoexlpaymentdata':
            wr.s3.to_csv(df=df,
                            path=f"s3://{combined_s3_bucket}/{combined_payment_kill_prefix}/{combined_payment_file_prefix}_{d}_{time_now}.csv")
        elif key == 'scetoexldonotworkaccounts':
            wr.s3.to_csv(df=df,
                            path=f"s3://{combined_s3_bucket}/{combined_payment_kill_prefix}/{combined_killfile_prefix}_{d}_{time_now}.csv")
    
        logger.info("Merged file is saved in a bucket")

    for obj in source_s3bucket.objects.filter(
            Prefix=source_prefix):
        if obj.size > 0:
            split_file_key = obj.key
            file_name = os.path.basename(split_file_key)
            copy_source = {
                'Bucket': source_s3_bucket,
                'Key': split_file_key}
            response = s3_client.copy_object(
                CopySource=copy_source,
                Bucket = processed_s3_bucket,
                Key=f"{processed_prefix}/{file_name}")
            if response['ResponseMetadata'][
                'HTTPStatusCode'] == 200:
                s3_client.delete_object(
                    Bucket = source_s3_bucket,
                    Key=split_file_key)
            else:
                message = f"{split_file_key} is not deleted"
                logger.info(message)
                function_step_alert(message)
                return
            
    logger.info("Files are deleted from Raw folder")
    message = "Files combined and successfully processed"
    logger.info(message)
    function_step_alert(message)
