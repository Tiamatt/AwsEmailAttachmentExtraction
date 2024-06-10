# Email Attachment Extraction and processing

## **Architecture**

The high-level architecture for our project is illustrated in the diagram below:

![Image description](TODO-add-later)


## Guidance

#### Step 1. Register your domain name in Route 53
    - If you purchased a new domain, don’t forget to verify it!

#### Step 2. Add an MX record to your domain's DNS configuration for Amazon SES email receiving
    - Use '10 inbound-smtp.us-east-1.amazonaws.com' for 'Value/Route traffic to'
TODO-provide with screenshot

#### Step 3. Run template No.1 for KMS CMK
    AWS CloudFormation sample template 
    - Create KMS customer managed key (CMK) for a specific or all AWS services
        Set up a KMS key with conditional key rotation, parameter-driven key specifications, 
        and a detailed key policy granting extensive permissions to the root account, 
        specific permissions to the Admin role, and limited permissions to S3 and SES services.
    - Create an alias for a KMS customer managed key (CMK) to use a friendly name rather than the key ID

#### Step 3. Run template No.2 for S3 buckets
    AWS CloudFormation sample template
    - Create an S3 bucket to store all project logs here
    - Create a policy for S3 bucket for logs to allow other S3 buckets to create and store logs
    - Create an S3 bucket to store raw emails (the whole content including attached files)
    - Create a policy for S3 bucket for raw emails to allow SES to create/store raw emails content
    - Create an S3 bucket to store attached files from emails
    - Create a policy for S3 bucket for email attachments to allow Lambda function to create/store and read email attachments

#### Step 4. Run template No.3 for SES and SNS
    AWS CloudFormation sample template
    - Create an SNS topic for incoming emails
    - Create a policy for SNS topic for incoming emails to allow SES to perform several actions (like publish messages, get attributes, set attributes, etc.) on SNS topic. Allow SES to trigger SNS topic for email's further processing
    - Create an empty SES receipt rule set to allow SES authenticate each received email 
    - Create an SES receipt rule to process incoming emails by storing them in an S3 bucket for incoming emails and sending notifications to an SNS topic for incoming email
    - Create an SES Identity by specifing a domain name that will be used to send emails to SES. Note, before you can use an SES identity, you first have to verify it (check email that domain name is attached to).

## Hiccups and struggles

#### Hiccup #1. Have to  use KMS CMK for SNS instead of default key
SNS topic must use an AWS KMS customer managed key instead of the default key (AWS/SNS)
This is because the default key policy doesn't include the required permissions for the AWS service to perform AWS KMS operations

#### Hiccup #2. Have to activate SES receipt rule set MANUALLY (in AWS Console)
There is a know issue that CloudFormation does not support setting an active receipt rule set yet for SES
Which means, there is no "Enabled: true" option on ReceiptRuleSet level
IMPORTANT!!! you currently have to go to console to activate it MANUALLY

#### Hiccup #3. No path specification for "Code" property for Lambda function 
You can't specify a local file link (such as '/lambda-for-email-parsing.py') under "Code:" -> "ZipFile:"
Instead, you must put in the function code itself. It is limited to 4096 bytes. 
If your code is bigger, (or alternatively) you can to upload the code to S3 first and use S3Bucket and S3Key.