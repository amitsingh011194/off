import base64
import gzip
import json
import io

def lambda_handler(event, context):
    output = []
    for record in event['records']:
        try:
            # Decode base64
            payload = base64.b64decode(record['data'])

            # If gzipped, decompress
            try:
                payload = gzip.GzipFile(fileobj=io.BytesIO(payload)).read()
            except OSError:
                pass  # not gzipped

            # Convert to JSON object (assuming input was text JSON string)
            data = json.loads(payload.decode("utf-8"))

            # Re-encode as NDJSON line
            json_line = json.dumps(data) + "\n"

            output_record = {
                'recordId': record['recordId'],
                'result': 'Ok',
                'data': base64.b64encode(json_line.encode("utf-8")).decode("utf-8")
            }
        except Exception as e:
            output_record = {
                'recordId': record['recordId'],
                'result': 'ProcessingFailed',
                'data': record['data']
            }

        output.append(output_record)

    return {"records": output}
