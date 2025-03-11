# -*- coding: utf-8 -*-
"""
Created on Thu Jan  2 14:06:58 2025

@author: tevsl
"""
import logging
import json
import datetime
import os

class GoogleCloudJSONFormatter(logging.Formatter):
    """
    Custom logging formatter to format log messages in Google Cloud JSON structure.
    """
    def format(self, record):
        log_record = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "logging.googleapis.com/sourceLocation": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            },
            "thread": record.threadName,
        }

        # Include additional context if available
        if hasattr(record, "extra"):
            log_record.update(record.extra)

        return json.dumps(log_record)

def setup_logging(syslog_file=None, syserr_file=None, console_level=logging.WARNING, syslog_level=logging.WARNING):
    """
    Set up logging configuration to output JSON-formatted logs in Google Cloud format
    to both the console and separate disk files for syslog and syserr, with default paths
    based on the operating system. If no log files are specified on a Linux instance,
    logs are sent directly to Google Cloud Logging.

    :param syslog_file: Path to the syslog file (default: system-appropriate location).
    :param syserr_file: Path to the syserr file (default: system-appropriate location).
    :param console_level: Logging level for console output (default: DEBUG).
    :param syslog_level: Logging level for syslog output (default: INFO).
    """
    logger = logging.getLogger()
    if logger.hasHandlers():
        # Avoid adding duplicate handlers if already configured
        return

    logger.setLevel(logging.DEBUG)

    if os.name != "nt":  # Only include Google Cloud Logging for Linux
        try:
            from google.cloud import logging as gcloud_logging

            # Initialize Google Cloud Logging client
            gcloud_client = gcloud_logging.Client()
            gcloud_client.setup_logging(log_level=syslog_level)

            # Add a StreamHandler for console output alongside Google Cloud Logging
            console_handler = logging.StreamHandler()
            console_handler.setLevel(console_level)
            console_handler.setFormatter(GoogleCloudJSONFormatter())
            logger.addHandler(console_handler)

            logger.info("Google Cloud Logging initialized with console output.")
            return  # Use Google Cloud Logging and console; no need for local files
        except ImportError:
            logger.warning("Google Cloud Logging library not available. Falling back to local logging.")

    # Determine default file locations based on the OS
    if syslog_file is None:
        syslog_file = os.path.join(
            "C:\\Logs" if os.name == "nt" else "/var/log",
            "application_syslog.json"
        )

    if syserr_file is None:
        syserr_file = os.path.join(
            "C:\\Logs" if os.name == "nt" else "/var/log",
            "application_syserr.json"
        )

    # Ensure the directories exist
    for file_path in [syslog_file, syserr_file]:
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    # Create JSON formatter for Google Cloud
    gcloud_formatter = GoogleCloudJSONFormatter()

    # StreamHandler for console output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)  # Set level based on parameter
    console_handler.setFormatter(gcloud_formatter)
    logger.addHandler(console_handler)

    # FileHandler for syslog output
    syslog_handler = logging.FileHandler(syslog_file, mode='a', encoding='utf-8')
    syslog_handler


# Example usage
if __name__ == "__main__":
    setup_logging()

    logger = logging.getLogger("example_logger")

    logger.info("Application started")
    logger.warning("Low disk space", extra={"extra": {"disk_space": "100MB"}})
    logger.error("Unhandled exception occurred", extra={"extra": {"user_id": 12345}})
