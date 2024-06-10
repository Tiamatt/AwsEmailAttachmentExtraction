                    # --------- START CODE  --------- #
                    import boto3
                    import email
                    import json
                    import os
                    from email import policy
                    import re
                    from datetime import datetime

                    # --------- Setup environment variables --------- #
                    EMAILS_DYNAMO_TABLE = os.environ['EMAILS_DYNAMO_TABLE']
                    ATTACHMENTS_BUCKET = os.environ['ATTACHMENTS_BUCKET']
                    EMAIL_PARSED_STATUS_NOTIFICATION_TOPIC = os.environ['EMAIL_PARSED_STATUS_NOTIFICATION_TOPIC']

                    # Main function
                    def lambda_handler(event, context):
                        print("START PROCESS")

                        try:
                            # Get message from SNS topic 
                            sns_message = get_sns_message(event)
                            new_event = json.loads(sns_message)
                            action = get_action(new_event)
                            source_email = get_source_email(new_event)
                            actionType = action['type']
                            if actionType != 'S3':
                                raise Exception('Expected action type to be S3, got: ' + actionType)
                            bucket_name = action['bucketName']
                            object_key = action['objectKey']
                            email_id = object_key
                        
                            # process raw email
                            raw_email_response = process_raw_email(bucket_name, object_key, source_email, email_id)
                            print(f"Response: {raw_email_response}")

                            # publish a success message in SNS topic
                            sns_response = publish_sns_message(raw_email_response)

                        except Exception as e:
                            print(f"An unexpected error occurred: {e}")

                        print("END PROCESS")
    
                    # Get notification message from SNS
                    def get_sns_message(sns_payload):
                        if 'Records' not in sns_payload:
                            print("No Records section")
                            raise Exception('No Records section')
    
                        if len(sns_payload['Records']) != 1:
                            print("Expected only 1 record")
                            raise Exception('Expected only 1 record')
    
                        sns_message = sns_payload['Records'][0]['Sns']['Message']
                        print(f"SNS message: {sns_message}")

                        return sns_message

                    # Get action from sns message
                    def get_action(new_event):
    
                        if 'receipt' not in new_event:
                            print("Invalid event, expected receipt section")
                            raise Exception('Invalid event, expected receipt section')
        
                        if 'action' not in new_event['receipt']:
                            print("Invalid event, expected receipt action section")
                            raise Exception('Invalid event, expected receipt action section')
      
                        action = new_event['receipt']['action']
                        print(f"SNS action: {action}")
    
                        return action

                    # Get source email from sns message
                    def get_source_email(new_event):

                        if 'mail' not in new_event:
                            print("Invalid event, expected mail section")
                            raise Exception('Invalid event, expected mail section')
        
                        if 'source' not in new_event['mail']:
                            print("Invalid event, expected email source section")
                            raise Exception('Invalid event, expected email source section')

                        source_email = new_event['mail']['source']
                        print(f"Source email: {source_email}")

                        if '=' in source_email:
                            source_email = source_email.split('=')
                            source_email = source_email[2]
    
                        return source_email

                    # Process raw email
                    def process_raw_email(bucket_name, object_key, source_email, email_id):
                        s3 = boto3.client('s3')
                        dynamodb = boto3.client('dynamodb')
    
                        # Retrieve the email stored in S3 that triggered this event
                        s3_raw_email = s3.get_object(Bucket=bucket_name, Key=object_key)

                        # Extract the email sender's address and, if present, decodes it if encoded
                        raw_email_str = s3_raw_email['Body'].read().decode('utf-8')
                        raw_email = \
                            email.parser.Parser(policy=policy.strict).parsestr(raw_email_str)

                        # Parse the email content
                        now = datetime.now()
                        dt_string = now.strftime('%d/%m/%Y %H:%M:%S')
                        attachment_index = 0
                        attachments = []
                        document_name_list = ''
                        for part in raw_email.walk():
                            # Check if there is any attached file in raw email
                            if part.is_attachment():
                                if len(part.get_filename()):
                                    # Handle when filename is present
                                    # a) Construct attachment_key by appending a sanitized version of the filename (removing all non-alphanumeric characters) to a base object_key followed by '/attachments/'.
                                    attachment_key = object_key + '/attachments/' + re.sub(r'[^a-zA-Z0-9]', '', part.get_filename())
                                    # b) Construct a job_tag using a combination of the first five characters of email_id and the sanitized filename
                                    job_tag = email_id[0:5] + '_' + re.sub(r'[^a-zA-Z0-9]','', part.get_filename())
                                    attachment_index += 1
                                else:
                                    # Handle when filename is missing
                                    # a) Create a unique identifier 
                                    attachment_id = str(attachment_index)
                                    # b) Construct attachment_key by appending a base object_key followed by '/attachments/' and a unique identifier
                                    attachment_key = object_key + '/attachments/' + attachment_id
                                    # c) Construct job_tag by appending the first five characters of email_id followed by '/attachments/' and a unique identifier
                                    job_tag = email_id[0:5] + '_' + attachment_id
                                    attachment_index += 1
            
                                # Save attachment in another S3 bucket
                                s3.put_object(Bucket=ATTACHMENTS_BUCKET, Key=attachment_key, Body=part.get_content())
                                document_name_list += part.get_filename() + ','
                                print(f"Document was successfully extracted and saved in '{ATTACHMENTS_BUCKET}'. Document name: '{part.get_filename()}'.")
            
                                # Save attachment details in DB
                                item = {
                                    'email_id': {'S': email_id},
                                    'subject': {'S': raw_email['subject']},
                                    'source': {'S': source_email},
                                    'document_name': {'S': part.get_filename()},
                                    'timestamp': {'S': dt_string},
                                }
                                dynamodb.put_item(TableName=EMAILS_DYNAMO_TABLE, Item=item, ReturnValues='NONE')
                                print(f"Document details were successfully saved in '{EMAILS_DYNAMO_TABLE}'. Document name: '{part.get_filename()}'.")
            
                                # Append attachments details  
                                attachments.append({
                                    'attachment_id': part.get_filename(),
                                    'content_type': part.get_content_type(),
                                    'key': attachment_key
                                })
     
                        response = {'email_id': email_id, 'attachments': attachments}
                        return response

                    def publish_sns_message(raw_email_response):
                        sns = boto3.client('sns')
                        sns_message = {
                                'subject': 'EMAIL_PARSED_STATUS',
                                'status': 'SUCCESS',
                                'details': raw_email_response
                                }
                        try:
                            # SNS messages are always strings - make the string a serialized version of custom object
                            # also it is required to wrap the custom message in 'default' property 
                            response = sns.publish(
                                    TopicArn=EMAIL_PARSED_STATUS_NOTIFICATION_TOPIC,
                                    Subject=sns_message['subject'],
                                    Message=json.dumps({'default': json.dumps(sns_message)}),
                                    MessageStructure='json'
                            )
                            message_id = response['MessageId']
                            print("Successfully published message to SNS topic")
                        except Exception as e:
                            print("Failed to publish message to SNS topic")
                            raise Exception(f'Failed to publish message to SNS topic. Error: {e}')
                        else:
                            return message_id

                        # Keep this comment for CloudFormation sake - there is an issue that doesn't make sense

                    # --------- END CODE  --------- #