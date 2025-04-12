# -*- coding: utf-8 -*-
"""
Created on Mon Sep 16 17:07:38 2024

@author: tevsl
"""
import boto3
import pickle
import io
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
s3_client = boto3.client('s3')

def get_presigned_url(bucket_name,object_key,expires_in=3600):
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': object_key},
        ExpiresIn=expires_in
    )
def get_last_modified_date(bucket_name, object_key):
    
    response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
        # Extract and return the LastModified date
    return response['LastModified']

def rename_s3_object(bucket_name, old_key, new_key):
    """
    Renames an object in an S3 bucket by copying it to a new key and deleting the old one.

    Args:
        bucket_name (str): The name of the S3 bucket.
        old_key (str): The current key (name) of the object.
        new_key (str): The new key (name) for the object.

    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    
    try:
        # Copy the object to the new key
        copy_source = {'Bucket': bucket_name, 'Key': old_key}
        s3_client.copy(copy_source, bucket_name, new_key)
        print(f"Object copied to new key: {new_key}")
        
        # Delete the old object
        s3_client.delete_object(Bucket=bucket_name, Key=old_key)
        print(f"Original object deleted: {old_key}")
        
        return True

    except ClientError as e:
        print(f"Error renaming object {old_key}: {e}")
        return False
   
def check_bucket_exists(bucket_name):

    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        # A ClientError is raised if the bucket does not exist or you do not have access to it
        error_code = int(e.response['Error']['Code'])
        if error_code == 403:
            raise PermissionError(f"Access to bucket '{bucket_name}' is forbidden (403 Forbidden).")
        elif error_code == 404:
            raise FileNotFoundError(f"Bucket '{bucket_name}' does not exist (404 Not Found).")
        else:
            raise e
    except NoCredentialsError:
        raise RuntimeError("AWS credentials not found.")
    except PartialCredentialsError:
        raise RuntimeError("Incomplete AWS credentials provided.")
        
def upload_file_to_s3(bucket_name, file_path, object_key=None,ExtraArgs=None):
    from pathlib import Path
    if not object_key:
        object_key=Path(file_path).name
        
    try:
        # Upload the file
        if ExtraArgs:
            s3_client.upload_file(file_path, bucket_name, object_key,ExtraArgs=ExtraArgs)
        else:
            s3_client.upload_file(file_path, bucket_name, object_key)
        print(f"File '{file_path}' uploaded successfully to '{bucket_name}/{object_key}'.")
    except Exception as e:
        print(f"Error occurred while uploading file {file_path}' to '{bucket_name}/{object_key}': {e}")
        raise
        
def upload_object_to_s3(bucket_name, object, object_key,ContentType=None):
    try:
        # Upload the file
        if ContentType:
            s3_client.put_object(Body=object, Bucket=bucket_name, Key=object_key,ContentType=ContentType)
        else:            
            s3_client.put_object(Body=object, Bucket=bucket_name, Key=object_key)
        print(f"File 'Upload successful to '{bucket_name}/{object_key}'.")
    except Exception as e:
        print(f"Error occurred while uploading object to {bucket_name}/{object_key} : {e}")
        
        
def retrieve_from_s3(bucket, key):
    # Implement the logic to retrieve content from S3 using boto3
    
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    return obj['Body'].read().decode('utf-8')

def delete_from_s3(bucket, key):
    """
    Delete an object from an S3 bucket.

    :param bucket: Name of the S3 bucket.
    :param key: Key of the object to delete.
    :return: True if the object was deleted, otherwise False.
    """
    try:
        # Check if the object exists
        s3_client.head_object(Bucket=bucket, Key=key)
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            print(f"Object {key} does not exist in bucket {bucket}.")
            return False
        else:
            print(f"Error checking existence of {key} in bucket {bucket}: {e}")
            return None
    try:
        # Delete the object
        s3_client.delete_object(Bucket=bucket, Key=key)
        print(f"Deleted {key} from {bucket}")
        return True
    except ClientError as e:
        # Handle the error
        print(f"Error deleting {key} from {bucket}: {e}")
        return False
        
def pickle_object_to_s3(bucket_name,the_object,object_key):

    # Pickle the object
    pickled_data = pickle.dumps(the_object)
    with io.BytesIO(pickled_data) as f:
        # Upload the pickled object to S3
        s3_client.upload_fileobj(f, bucket_name, object_key)
    print(f"Object successfully pickled and uploaded to S3 at {bucket_name}/{object_key}")
    
def pickle_object_from_s3(bucket_name, object_key):

    try:
        # Attempt to retrieve the object from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        # Read the object's content
        object_data = response['Body'].read()
        # Unpickle and return the object
        return pickle.loads(object_data)

    except ClientError as e:
        # If the object does not exist, return None
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"Object {object_key} not found in bucket {bucket_name}.")
            return None
        else:
            # If there's another issue, re-raise the exception
            raise
            
def list_keys_in_bucket(bucket):
    """
    Helper function to list all object keys in an S3 bucket.
    
    :param bucket: The name of the S3 bucket.
    :return: A set of all object keys in the bucket.
    """
    keys = set()
    
    # Paginate through all objects in the bucket
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket):
        if 'Contents' in page:
            for obj in page['Contents']:
                keys.add(obj['Key'])
    
    return keys

def get_s3_url(bucket, key):
    """
    Helper function to generate the correct S3 URL for an object, considering AWS regions.
    
    :param bucket: The name of the S3 bucket.
    :param key: The object key.
    :return: The correct URL of the object.
    """

    # Get the region of the bucket
    bucket_location = s3_client.get_bucket_location(Bucket=bucket)
    region = bucket_location['LocationConstraint']
    
    # Construct the correct URL based on the region
    if region is None or region == 'us-east-1':
        url = f"https://{bucket}.s3.amazonaws.com/{key}"
    else:
        url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    
    return url
if __name__ == '__main__':
    #print(list_keys_in_bucket("goldendomevt.com"))
    #print(pickle_object_to_s3('testdeepgramaudio',{"gloppy":"glop"},"glop"))
    #print(delete_from_s3('testdeepgramaudio','glop'))
    #print(rename_s3_object('testdeepgramaudio','glop','VTHouseFloor_2025-01-14_10-19.json'))
    pass
