# -*- coding: utf-8 -*-
"""
Created on Tue Dec 17 16:03:54 2024

@author: tevsl
"""

import boto3
import os
import logging
import json
from deepgram import DeepgramClient, PrerecordedOptions
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda function to generate an S3 presigned URL and invoke Deepgram API using its SDK.
    Bucket name and file key are passed dynamically in query parameters.
    """
    # Deepgram API Key from environment variable
    DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')
    if not DEEPGRAM_API_KEY:
        logger.error("Missing Deepgram API Key in environment variables.")
        return {"statusCode": 500, "body": json.dumps({"error": "Missing Deepgram API Key"})}
            # Parse query parameters
    for record in event['Records']:
        try:
            bucket_name = record['s3']['bucket']['name']
            file_key = record['s3']['object']['key']

            #if file_key.endswith('.wav') or file_key.endswith('.webm') or file_key.endswith('.m4a'):
            logger.info(f"Processing file: {file_key} in bucket: {bucket_name}")
            process_request(DEEPGRAM_API_KEY,bucket_name, file_key,expiration=3600)
        #else:
                #logger.info(f"Skipped unsupported file type {file_key}")
        except Exception as e:
            logger.error(f"Error processing record: {record}")
            logger.error(f"Exception: {e}")

def process_request(DEEPGRAM_API_KEY,bucket_name,file_key,expiration):
    split=file_key.split(".")
    if len(split)==2:
        destination_transcript_key=split[0]+'.json'
    elif len(split)==1:
        file_key+='.wav'
        destination_transcript_key=file_key+'.json'
    logger.info(f"Will transcribe {file_key} to {destination_transcript_key} in bucket {bucket_name}.")
    s3_client = boto3.client('s3')
    deepgram = DeepgramClient(DEEPGRAM_API_KEY)
    try:
        get_url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket_name, "Key": file_key},
            ExpiresIn=expiration,
        )
        put_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": bucket_name,
                "Key": destination_transcript_key,
                "ContentType": "application/json",
            },
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        
    
    logger.info("Presigned URLs generated successfully.")
    
    try:
        options: PrerecordedOptions = PrerecordedOptions(
            model="nova-2-meeting",
            utterances=True,
            punctuate=True,
            diarize=True,
            paragraphs=True,
            callback=put_url,
            callback_method= "put",
            )
  
        source = {"url": get_url}
        print(source)
        response = deepgram.listen.rest.v("1").transcribe_url(source, options)
        logger.info(f"deepgram response: {response.to_json()}")

        
    except Exception as e:
        logger.error(f"Deepgram error: {str(e)}")
      
