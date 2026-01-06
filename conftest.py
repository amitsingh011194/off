import boto3
import dateutil.tz
import json
import logging
import math
import os
import time

from botocore.config import Config
from botocore.exceptions import ClientError
from datetime import datetime


logger = logging.getLogger()
logger.setLevel(os.environ.get('log_level', 'INFO'))


USE_MPS_RATE_LIMITING = os.environ.get('USE_MPS_RATE_LIMITING', 'false').lower() in ('true', '1', 't')

if USE_MPS_RATE_LIMITING:
    try:
        NUMBER_MPS_RATE_LIMIT = int(os.environ['NUMBER_MPS_RATE_LIMIT'])
        RESERVED_CONCURRENCY = int(os.environ['RESERVED_CONCURRENCY'])
    except KeyError:
        logger.error("MPS rate limiting is enabled but NUMBER_RATE_LIMIT or RESERVED_CONCURRENCY is not set")
        raise

    RATE_LIMIT_WINDOW = float(os.environ.get('RATE_LIMIT_WINDOW', 1.0))
    INSTANCE_MPS_RATE_LIMIT = math.ceil(NUMBER_MPS_RATE_LIMIT // RESERVED_CONCURRENCY)
    logger.info(f"MPS rate limiting is enabled. instance rate limit is {INSTANCE_MPS_RATE_LIMIT}")
else:
    logger.info("MPS rate limiting is not enabled")

SENT_QUEUE_URL = os.environ['SENT_QUEUE_URL']
CONFIGURATION_SET_NAME = os.environ['CONFIGURATION_SET_NAME']
TIME_ZONE = os.environ.get('TIME_ZONE', 'US/Eastern')
tz = dateutil.tz.gettz(TIME_ZONE)
WEEKDAY_START_TIME = datetime.strptime(str(os.environ.get('WEEKDAY_START_TIME', '1:00PM')), '%I:%M%p').time()
WEEKDAY_END_TIME = datetime.strptime(str(os.environ.get('WEEKDAY_END_TIME', '6:00PM')), '%I:%M%p').time()
SATURDAY_START_TIME = datetime.strptime(str(os.environ.get('SATURDAY_START_TIME', '1:00PM')), '%I:%M%p').time()
SATURDAY_END_TIME = datetime.strptime(str(os.environ.get('SATURDAY_END_TIME', '6:00PM')), '%I:%M%p').time()


config = Config(
   retries = {
      'max_attempts': 10,
      'mode': 'standard'
   }
)
sqs_client = boto3.client("sqs")
eum_client = boto3.client('pinpoint-sms-voice-v2', config=config)


def lambda_handler(event, context):
    logger.debug(f"Event payload for sms sender: {event}")
    message_tracker_dict = {}
    message_batch = []
    failed_message_ids = set()
    start_time = time.time()
    parts_sent = 0

    for i, record in enumerate(event['Records']):
        try:
            body = record["body"]
            body = json.loads(body)
            message_id = record['messageId']
            batch_msg_id = str(i)
            message_tracker_dict[batch_msg_id] = message_id
            logger.debug(body)
            origination_number = body['senderphonenumber']
            to_sms = body["countrycode"].replace(" ", "") + body['to_num']

            logger.debug(f'recipient is {body["to_num"]}')
            curr_datetime = datetime.now(tz)

            message_parts_over_limit = False
            over_limit_delay = 0

            if USE_MPS_RATE_LIMITING:
                message_parts = calculate_message_parts(body['message'])
                logger.debug(f"message_parts is {message_parts}")

                if message_parts > INSTANCE_MPS_RATE_LIMIT:
                    logger.debug(f"Message parts over instance rate limit: {message_parts} > {str(INSTANCE_MPS_RATE_LIMIT)}")
                    over_limit_delay = message_parts / INSTANCE_MPS_RATE_LIMIT
                    logger.debug(f"calculated delay is {over_limit_delay} seconds")
                    message_parts_over_limit = True

                else:
                    if parts_sent + message_parts > INSTANCE_MPS_RATE_LIMIT:
                        logger.debug(f"sum of parts_sent and message_parts is over instance rate limit: {parts_sent + message_parts} > {INSTANCE_MPS_RATE_LIMIT}")
                        elapsed_time = time.time() - start_time
                        logger.debug(f"elapsed time is {elapsed_time}")
                        if elapsed_time < RATE_LIMIT_WINDOW:
                            wait_time = RATE_LIMIT_WINDOW - elapsed_time
                            logger.debug(f"Less than rate limit ({RATE_LIMIT_WINDOW} seconds) passed: {elapsed_time}. Waiting {wait_time} seconds")
                            time.sleep(wait_time)  # Wait until the next window
                            # Reset start_time and parts_sent count for the new window
                            start_time = time.time()
                            parts_sent = 0
                            logger.debug("reset parts sent count and start time")
                        else:
                            logger.debug(f"More than rate limit ({RATE_LIMIT_WINDOW} seconds) passed: {elapsed_time}. resetting time and parts sent count")
                            start_time = time.time()
                            # Reset start_time and parts_sent count for the new window
                            parts_sent = 0
                            logger.debug("reset parts sent count and start time")

            if (body['communicationmode'] == 'sms') and (is_go_time(curr_datetime) == True):
                message_body = body['message']
                logger.debug("Sending SMS message.")
                logger.debug(f'origination_number:{origination_number}')
                logger.debug(f'destination_number:{to_sms}')

                response = send_sms_message(
                    origination_number,
                    to_sms,
                    message_body
                )

                if USE_MPS_RATE_LIMITING:
                    if message_parts_over_limit:
                        logger.debug(f"Waiting {over_limit_delay} secs for overlimit msg")
                        time.sleep(over_limit_delay)
                        parts_sent = 0
                        start_time = time.time()
                    else:
                        parts_sent += message_parts

            elif body['communicationmode'] == 'sms':
                logger.info('Time beyond permitted window of operation. Hence not sending')
                continue
            else:
                logger.error('Error occurred when sending sms as appropriate communnication_channel could not be found')
                continue

        except Exception:
            logger.exception("Error occurred when sending sms")
            failed_message_ids.add(message_id)
        else:
            try:
                result_message_id = response['MessageId']
                body['action_id'] = result_message_id
                body['source_action_id'] = result_message_id
                body['from'] = origination_number

                message_batch.append(
                    {
                        "Id": batch_msg_id,
                        "MessageBody": json.dumps(body)
                    }
                )
            except Exception:
                logger.exception("Error occurred when preparing message for sending to sqs")

            if len(message_batch) == 10:
                publish_to_queue(SENT_QUEUE_URL, message_batch, message_tracker_dict)
                message_batch = []

    if message_batch:
        publish_to_queue(SENT_QUEUE_URL, message_batch, message_tracker_dict)

    if failed_message_ids:
        logger.error(f"Failed to process messages with ids: {failed_message_ids}")
        return {
            'batchItemFailures': [{'itemIdentifier': msg_id} for msg_id in
                                  failed_message_ids]
        }


def send_sms_message(origination_number, destination_number, message):
    """
    Sends an SMS message using End User Messaging.

    Args:
        origination_number: The phone number to use as the sender of the SMS message.
        destination_number: The phone number to send the SMS message to.
        message: The body of the SMS message.

    Returns:
        The response from the AWS End User Messaging service, including the status of the message
        and any relevant metadata.

    Raises:
        Exception: If an error occurs while sending the SMS message.
    """
    logger.info(f"destination number is {destination_number}")
    logger.info(f"sending message: {message}")
    try:
        response = eum_client.send_text_message(
            DestinationPhoneNumber=destination_number,
            OriginationIdentity=origination_number,
            MessageBody=message,
            MessageType='TRANSACTIONAL',
            ConfigurationSetName=CONFIGURATION_SET_NAME
        )

        logger.info(f"End User Messaging response: {response}")
        result_status_code = response['ResponseMetadata']['HTTPStatusCode']

        if result_status_code == 200:
            logger.info("Message sent successfully")
            return response
        else:
            logger.error(f"Unexpected End User Messaging result status code: {result_status_code}")
            raise Exception("Unexpected SNS result status code")
    except Exception:
        logger.error("Failed to send SMS message to End User Messaging.")
        raise


def publish_to_queue(sqs_url, entries, message_tracker_dict):
    """
    Publishes a batch of messages to the Amazon SQS queue at the given URL.

    :param sqs_url: The URL of the Amazon SQS queue to which the messages will be published.
    :param entries: A list of dictionaries, where each dictionary represents a message to be published to the queue.
    :return: None
    """
    logger.debug(
        f"Publishing {len(entries)} messages to the queue at URL: {sqs_url}")
    logger.debug(f"Message entries: {entries}")
    try:
        response = sqs_client.send_message_batch(
            QueueUrl=sqs_url,
            Entries=entries
        )
        check_sqs_response(response, message_tracker_dict)
    except ClientError:
        logger.exception(f"failed to add message batch to sqs queue. MessageIds in batch: {message_tracker_dict.values()}")


def check_sqs_response(response, message_tracker_dict):
    """
    validate sqs response, for errors
    """
    logger.debug(response)
    if 'Failed' in response:
        for message in response['Failed']:
            # failure_ids.add(message['Id'])
            logger.error(
                f'Failed to add messageId {message_tracker_dict[message["Id"]]} to the queue: {json.dumps(message)}')
    else:
        logger.info('Successfully sent messages to the queue')


class MaxRetryReachedError(Exception):
    pass

def calculate_message_parts(message):
    gsm_7_limit = 160
    ucs_2_limit = 70

    if is_gsm0338_encoded(message):
        encoding_limit = gsm_7_limit
        part_limit = 153  # 160 - 7 (concatenation headers)
    else:
        encoding_limit = ucs_2_limit
        part_limit = 67  # 70 - 3 (concatenation headers)


    message_length = len(message)
    if message_length <= encoding_limit:
        return 1
    else:
        return (message_length + part_limit - 1) // part_limit


GSM_0338_CHARSET = (
    '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ`¿abcdefghijklmnopqrstuvwxyzäöñüà'
)
GSM_0338_ESCAPED = {
    '\x0c': '\x1b\x0a',  # Form feed
    '^': '\x1b\x14',
    '{': '\x1b\x28',
    '}': '\x1b\x29',
    '\\': '\x1b\x2f',
    '[': '\x1b\x3c',
    '~': '\x1b\x3d',
    ']': '\x1b\x3e',
    '|': '\x1b\x40',
    '€': '\x1b\x65'
}



def is_gsm0338_encoded(message):
    for char in message:
        if char not in GSM_0338_CHARSET:
            if char in GSM_0338_ESCAPED:
                continue
            return False
    return True

def is_go_time(curr_datetime):
    """
    Check if current time is within allowed windows.
    curr_datetime: timezone-aware datetime object
    Returns True if current time is within the time window for the day.
    Sunday is no communication (always False).
    """
    curr_time = curr_datetime.time()
    weekday = curr_datetime.weekday() 

    time_windows = {
        range(0, 5): (WEEKDAY_START_TIME, WEEKDAY_END_TIME),
        range(5, 6): (SATURDAY_START_TIME, SATURDAY_END_TIME) 
    }

    # Find the applicable time window for the day
    for days, (start, end) in time_windows.items():
        if weekday in days:
            if start <= end:
                return start <= curr_time <= end
            return curr_time >= start or curr_time <= end

    return False
