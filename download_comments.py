#!/usr/bin/env python3
# coding=utf-8
"""
This script retrieves updated Jira issues and writes it to STDOUT in JSON format. Configurations are provided through an INI file.
You need to configure your Jira personal access token and possibly SSL client certificates before proceeding.
"""
import os
import re
import sys
import json
import time
import argparse
import datetime
import logging
import functools
from typing import Any, Dict, List, Tuple
from configparser import ConfigParser, NoOptionError, BasicInterpolation

# these 2 modules need to be installed with pip
import jira
import custom_lib
from jira2markdown import convert as convert_to_md

CHECKPOINT_TIME_FORMAT="%Y-%m-%dT%H:%M:%S%z"
#######################################################################


logging.basicConfig(format='%(asctime)s %(levelname)s [%(name)s]: %(message)s', level=logging.WARNING)
logger = logging.getLogger("jirasync")
logger.setLevel(logging.INFO)


JIRA_USER_REF_REGEX = re.compile("\[~([^\]]+)\]")

def get_user_references_from_comment(jira_ref, comment:str, references_cache: dict) -> list:
    # provides a list of jira user objects referenced within the comment's body
    if references_cache is None:
        references_cache = {}
    
    referenced_jira_users = []
    # used to avoid duplicating data within the references list
    already_added_users = set()
    # search all user references within the comment...
    for u in re.findall(JIRA_USER_REF_REGEX, comment):
        # ...and keep only those which have not yet been added to the final list (in case some are duplicates)
        if u not in already_added_users:
            try:
                referenced_jira_users.append(references_cache[u])
            except KeyError:
                try: 
                    ju = jira_ref.user(u)
                    references_cache[u] = ju
                    referenced_jira_users.append(ju)
                except: 
                    logger.warning(f"User '{u}' not found in Jira")
        already_added_users.add(u)
    return referenced_jira_users

def process(source_jira, JQL):
    try:
        # log a monitoring event
        _new_checkpoint = None
        t = time.time()
        tot_skipped = 0
        tot_processed = 0
        # latest_update_retrieved is used to track which is the latest updated ts of the issues returned by the JQL. 
        # It will in the end be the new checkpoint stored within the configuration file
        logger.info(f"Searching for issues on source jira instance through JQL:\n\t{JQL}")
        user_references_cache = {}
        i = 0
        for issue in custom_lib.get_jira_issues(source_jira, JQL, fields=["summary", "issuetype", "priority", "reporter", "assignee", "created"], expand=None, batch_size=100):
            i+=1
            logger.info(f"Processing issue {i}: {issue.key}")
            prev_created = None
            comment_seq = 0
            c_cnt = 0
            for comment in source_jira.comments(issue):
                c = dict(
                    ticket = dict(
                        key = issue.key,
                        title = issue.fields.summary,
                        issuetype = issue.fields.issuetype.name,
                        reporter = issue.fields.reporter.name,
                        assignee = issue.fields.assignee.name if issue.fields.assignee else None,
                        priority = issue.fields.priority.name,
                        created = issue.fields.created,
                        created_epoch = custom_lib.jira_timestamp_to_epoch(issue.fields.created)
                    ),
                    comment = convert_to_md(comment.body),
                    author = comment.author.displayName,
                    author_email = comment.author.emailAddress,
                    seq = comment_seq, 
                    created = comment.created,
                    updated = comment.updated,
                    created_epoch = custom_lib.jira_timestamp_to_epoch(comment.created),
                    updated_epoch = custom_lib.jira_timestamp_to_epoch(comment.updated),
                    referenced_users = [ju.emailAddress for ju in get_user_references_from_comment(source_jira, comment.body, user_references_cache)]
                )
                
                comment_created_dt = custom_lib.jira_timestamp_to_dt(comment.created)
                if not prev_created is None: 
                    c["delta_created_h"] = round((comment_created_dt - prev_created).total_seconds()/3600.0, 1)
                prev_created = comment_created_dt
                comment_seq+=1
                print(json.dumps(c, sort_keys=True))
            logger.debug(f"    Issue {i} {issue.key} has {c_cnt} comments")
    except KeyboardInterrupt as e:
        raise e
    except Exception as e:
        logger.exception(e)
        raise e

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This script retrieves updated Jira issues from a "source" jira instance and updates corresponding issues onto a "target" jira instance. Configurations are provided through an INI file. You need to configure your Jira personal access token and possibly SSL client certificates before proceeding.')
    parser.add_argument('-c', '--config_file', required=True, help='Path to a configuration file to provide endpoint information')
    parser.add_argument('-s', '--stanza', default="source", help='Configuration stanza within the configuration file representing the Jira instance to be used as source. Default: "%(default)s"')
    args = parser.parse_args()


    logger = logging.getLogger("jirasync")
    logger.info(f'Executing jira sync with config_file="{args.config_file}" stanza="{args.stanza}"')
    script_start_time = time.time()
    # Set through a configuration in the config file
    latest_update_retrieved = None
    JQL = None
    try:
        if not os.path.isfile(args.config_file):
            logger.error(f"Configuration file '{args.config_file}' not found.")
            raise FileNotFoundError(args.config_file)
        
        # Import configuration file
        configs=ConfigParser(interpolation=custom_lib.EnvInterpolation())
        configs.read(args.config_file)

        #Checks if the section configuration is in the config file
        if not configs.has_section(args.stanza):
            logger.error(f'Missing stanza "{args.stanza}" in file "{args.config_file}"')
            raise ValueError(f"Invalid source stanza '{args.stanza}' specified for config file '{args.config_file}'")
        
        try:
            # connectivity to SOURCE jira
            config_options = configs.options(args.stanza)
            SOURCE_JIRA_SERVER=configs.get(args.stanza,"jira_server")
            SOURCE_JIRA_TOKEN=configs.get(args.stanza,"jira_token")
            SOURCE_CLIENT_CRT=configs.get(args.stanza,'client_crt') if "client_crt" in config_options else None
            SOURCE_CLIENT_KEY=configs.get(args.stanza,'client_key') if "client_key" in config_options else None
            JQL=configs.get(args.stanza,'jql')
       
            source_jira = custom_lib.get_jira_connection(server=SOURCE_JIRA_SERVER, token=SOURCE_JIRA_TOKEN, client_TLS_cert=SOURCE_CLIENT_CRT, client_TLS_key=SOURCE_CLIENT_KEY, logger=logger)
        except NoOptionError as e:
            msg = f"Missing configuration in stanza {args.stanza} of file {args.config_file}: {e}"
            logger.error(msg)
            raise Exception(msg) from e
        except custom_lib.JiraRelatedError as e:
            msg = f"Connection to jira server failed: {e.status_code} {e.reason}"
            logger.error(msg)
            raise Exception(msg) from e
        except ValueError as e:
            msg = f"Invalid configuration provided: {str(e)}"
            logger.error(msg)
            raise Exception(msg) from e
        except Exception as e:
            msg = f"Unexpected error occurred. Aborting. {str(e)}"
            logger.exception(msg)
            raise Exception(msg) from e 
    
        process(source_jira, JQL)

    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.exception(f"Uncaught Exception raised. {str(e)}")
    else:
        logger.info("Execution successful")
    finally:
        logger.info(f"Executed JQL: {JQL}")
        logger.info("Exiting")
