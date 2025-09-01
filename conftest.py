import boto3
import dateutil.tz
import json
import logging
import math
import os
import random
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
TIME_ZONE = os.environ.get('TIME_ZONE', 'US/Eastern')
tz = dateutil.tz.gettz(TIME_ZONE)
START_TIME = datetime.strptime(str(os.environ.get('START_TIME', '1:00PM')), '%I:%M%p')
END_TIME = datetime.strptime(str(os.environ.get('END_TIME', '6:00PM')), '%I:%M%p')

PINPOINT_MAX_RETRIES = int(os.environ.get('PINPOINT_MAX_RETRIES', 10))
PINPOINT_MAX_RETRY_DELAY = float(os.environ.get('PINPOINT_MAX_RETRY_DELAY', 10))
PINPOINT_RETRY_BASE_DELAY = float(os.environ.get('PINPOINT_RETRY_BASE_DELAY', 0.3))
PINPOINT_RETRY_JITTER = float(os.environ.get('PINPOINT_RETRY_BASE_DELAY', 0.25))


config = Config(
   retries = {
      'max_attempts': 10,
      'mode': 'standard'
   }
)
sqs_client = boto3.client("sqs")
pinpoint_client = boto3.client('pinpoint', config=config)


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
            app_id = body['app_id']
            origination_number = body['senderphonenumber']
            keyword = body['keyword']
            to_sms = body["countrycode"].replace("+", "").replace(" ", "") + body['to_num']

            logger.debug(f'recipient is {body["to_num"]}')
            curr_datetime = datetime.now(tz)

            if USE_MPS_RATE_LIMITING:
                message_parts = calculate_message_parts(body['message'])
                logger.debug(f"message_parts is {message_parts}")

                if message_parts > INSTANCE_MPS_RATE_LIMIT:
                    logger.warning(f"Can't use rate limiting for this message. Message parts over instance rate limit: {message_parts} > {str(INSTANCE_MPS_RATE_LIMIT)}")
                else:
                    if parts_sent + message_parts > INSTANCE_MPS_RATE_LIMIT:
                        logger.debug(f"message parts over instance rate limit: {parts_sent + message_parts} > {INSTANCE_MPS_RATE_LIMIT}")
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
                origination_number = origination_number
                destination_number = to_sms
                message_body = body['message']
                message_type = 'TRANSACTIONAL'
                logger.debug("Sending SMS message.")
                logger.debug(f'app_id:{app_id}')
                logger.debug(f'origination_number:{origination_number}')
                logger.debug(f'destination_number:{destination_number}')

                response = send_sms_message(
                    app_id,
                    origination_number,
                    destination_number,
                    message_body,
                    message_type,
                    keyword
                )

                if USE_MPS_RATE_LIMITING:
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
                result_message_id = response['MessageResponse']['Result'][to_sms]['MessageId']
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


def send_sms_message(app_id, origination_number, destination_number, message,
                     message_type, keyword):
    """
    Sends an SMS message using the AWS Pinpoint service.

    Args:
        app_id: The ID of the AWS Pinpoint app to use.
        origination_number: The phone number to use as the sender of the SMS message.
        destination_number: The phone number to send the SMS message to.
        message: The body of the SMS message.
        message_type: The type of SMS message. This can be one of TRANSACTIONAL or PROMOTIONAL.
        keyword: The SMS keyword to use. This is used to identify the type of message,
            and is usually a short word or phrase.

    Returns:
        The response from the AWS Pinpoint service, including the status of the message
        and any relevant metadata.

    Raises:
        Exception: If an error occurs while sending the SMS message.
    """
    logger.info(f"sending message: {message}")
    for attempt in range(PINPOINT_MAX_RETRIES + 1):
        try:
            response = pinpoint_client.send_messages(
                ApplicationId=app_id,
                MessageRequest={
                    'Addresses': {destination_number: {'ChannelType': 'SMS'}},
                    'MessageConfiguration': {
                        'SMSMessage': {
                            'Body': message,
                            'MessageType': message_type,
                            'Keyword': keyword,
                            'OriginationNumber': origination_number}}})

            result_status_code = response['MessageResponse']['Result'][destination_number]['StatusCode']

            if result_status_code == 200:
                logger.info("Message sent successfully")
                return response
            elif result_status_code == 429:
                if attempt >= PINPOINT_MAX_RETRIES:
                    logger.error(f"Reached Max retry limit ({PINPOINT_MAX_RETRIES}). Failed to send sms message. Pinpoint response: {response}")
                    raise MaxRetryReachedError

                # exponential backoff with jitter
                delay = min(PINPOINT_RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, PINPOINT_RETRY_JITTER), PINPOINT_MAX_RETRY_DELAY)
                logger.info(f"Too Many Requests response. Retry number: {attempt + 1}. Retrying in {delay} secs...")
                time.sleep(delay)
            else:
                logger.error(f"Unexpected Pinpoint result status code. Pinpoint response: {response}")
                raise Exception("Unexpected Pinpoint result status code")
        except Exception:
            logger.error("Failed to send Pinpoint sms message.")
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
    curr_time = curr_datetime.strftime('%I:%M%p')
    curr_time = datetime.strptime(curr_time, '%I:%M%p')
    return_val = START_TIME <= curr_time <= END_TIME

    return return_val
