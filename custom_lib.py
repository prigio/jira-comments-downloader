#!/usr/bin/env python3
# coding=utf-8
"""
This script retrieves history data from Jira issues and writes it to a file. Configurations are provided through an INI file.
You need to configure your username/password and possibly Highway SSL client certificates before proceeding.
"""
import os
import re
import sys
import time
import logging
import datetime
from typing import List
from configparser import BasicInterpolation

# python3 -m pip install jira
import jira

#######################################################################
# ConfigParser functionality extension
#######################################################################
class EnvInterpolation(BasicInterpolation):
    """Interpolation which expands environment variables in values."""
    #https://stackoverflow.com/questions/26586801/configparser-and-string-interpolation-with-env-variable
    def before_get(self, parser, section, option, value, defaults):
        value = super().before_get(parser, section, option, value, defaults)
        return os.path.expandvars(value)

#######################################################################
# JIRA-related functions
#######################################################################
class JiraRelatedError(Exception):
    def __init__(self, reason, status_code=None):
        self.reason = reason
        self.message = reason
        self.status_code = status_code
    def __str__(self):
        return self.message

def jira_timestamp_to_dt(ts:str) -> datetime.datetime:
    # https://docs.python.org/3/library/re.html#re.sub
    return datetime.datetime.strptime(re.sub("\.\d\d\d",".000", ts, 1), "%Y-%m-%dT%H:%M:%S.000%z") if ts else None

def jira_timestamp_to_epoch(ts:str) -> float:
    # https://docs.python.org/3/library/re.html#re.sub
    return jira_timestamp_to_dt(ts).timestamp() if ts else None

# this function call jira and tries to connect with it
def get_jira_connection(server:str, token:str, client_TLS_cert:str=None, client_TLS_key:str=None, logger:logging.Logger=None) -> jira.client.JIRA:
    if not logger:
        logger = logging.getLogger("jiraconnection")
    # Connects to Jira and returns a Jira object
    jira_options=None
    if client_TLS_cert != None and client_TLS_key != None: #credential checking
        if not os.path.isfile(client_TLS_cert):
            raise FileNotFoundError(client_TLS_cert, "client certificate file not found")
        if not os.path.isfile(client_TLS_key):
            raise FileNotFoundError(client_TLS_key, "client key file not found")
        jira_options = {"client_cert": (client_TLS_cert, client_TLS_key)}
    try:
        logger.info(f'Connecting to Jira on "{server}" with token "{token[:4]}..."')
        j = jira.JIRA(server=server, token_auth=token, options=jira_options)
        logger.info(f'Jira connected as user "{j.session().name}" to "{server}"')
        return j
    except jira.exceptions.JIRAError as e:
        raise JiraRelatedError(f"Connection to '{server}' failed: JIRAError: {e.text}", status_code=e.status_code ) from e
    except RecursionError as e:
        raise JiraRelatedError(f"Connection to '{server}' failed: RecursionError. (Check authentication credentials) - {e}") from e
    except FileNotFoundError as e:
        raise JiraRelatedError(f"Jira connection '{server}' failed: FileNotFoundError. Certificate files not found. {e}") from e

def get_jira_issues(jira_client: jira.client.JIRA, jql: str, fields: list = None, expand=None, batch_size: int = 100):
    """ iterator which collects the issues from jira using the provided jira_client and jql query, and 'yields' them one by one"""
    if not isinstance(jira_client, jira.client.JIRA):
        raise ValueError("get_jira_issues: Invalid jira client")
    elif jql in (None, ""):
        raise ValueError("get_jira_issues: Invalid JQL")
    
    def _robust_search_issues(jira_client: jira.client.JIRA, jql: str, fields: list = None, expand=None, max_results:int=100, start_at:int = None, retries:int=5, wait_between_retries_s:int=60):
        performed_calls = 0
        while performed_calls < retries:
            performed_calls+=1
            try:
                return jira_client.search_issues(jql, fields=fields, expand=expand, maxResults=max_results, startAt=start_at)
            except jira.exceptions.JIRAError as e:
                # 500 - internal server error
                # 503 - service unavailable
                if e.status_code in (500, 503) and performed_calls < retries:
                    # wait and decrease
                    time.sleep(performed_calls * wait_between_retries_s)
                else:
                    raise e
    try:
        start_at = 0
        tot_results = None
        issue = None
        while tot_results == None or start_at < tot_results:
            # Search returns first 50 results, `maxResults` must be set to exceed this
            # https://jira.readthedocs.io/en/master/api.html#jira.JIRA.search_issues
            # response = jira_client.search_issues(jql, fields=fields, expand=expand, maxResults=batch_size, startAt=start_at)
            response = _robust_search_issues(jira_client, jql, fields=fields, expand=expand, max_results=batch_size, start_at=start_at, retries=5, wait_between_retries_s=45)
            # total # of issues the jql returns
            tot_results = response.total
            start_at += len(response)
            for issue in response.iterable:
                yield issue
    except jira.exceptions.JIRAError as e:
        raise JiraRelatedError(f"get_jira_issues: JQL query ERROR when executing search_issues() function - jql='{jql}', tot_results={tot_results}, start_at={start_at}, last_returned_issue={issue} - {e.text}", status_code=e.status_code) from e


