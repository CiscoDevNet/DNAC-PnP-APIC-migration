#!/usr/bin/env python
from __future__ import print_function
import json
import requests
import time
# turn off warninggs
requests.packages.urllib3.disable_warnings()
import re
import os
import logging
import hashlib
from argparse import ArgumentParser
from dnacentersdk import api

# create a logger
logger = logging.getLogger(__name__)

class TaskTimeoutError(Exception):
    pass

class TaskError(Exception):
    pass

def wait_for_task(dnac, taskid, retry=2, timeout=10):
    start_time = time.time()
    first = True
    while True:
        result = dnac.task.get_task_by_id(taskid)

        # print json.dumps(response)
        if result.response.endTime is not None:
            return result
        else:
            # print a message the first time throu
            if first:
                logger.debug("Task:{} not complete, waiting {} seconds, polling {}".format(taskid, timeout, retry))
                first = False
            if timeout and (start_time + timeout < time.time()):
                raise TaskTimeoutError("Task %s did not complete within the specified timeout "
                                       "(%s seconds)" % (taskid, timeout))

            logging.debug("Task=%s has not completed yet. Sleeping %s seconds..." % (taskid, retry))
            time.sleep(retry)

        if result.response.isError == "True":
            raise TaskError("Task %s had error %s" % (taskid, result.response.progress))

    return response

def atoi(text):
    return int(text) if text.isdigit() else text

# natural sort for templates
def natural_sort(templatelist):
    return sorted(templatelist, key=lambda template: [ atoi(c) for c in re.split('(\d+)', template)])

def get_sha1(data):
    myhash = hashlib.sha1(data.encode('utf-8'))
    return(myhash.hexdigest())

class Template(object):
    def __init__(self, dnac, name):
        self.dnac = dnac
        self.name = name
        self.projectId = self._get_project_id()
        self.templateid = None
        self.sha1 = None

    def update(self, body):
        # update template body
        logger.debug(self.templateid)
        devicetypes = [{"productFamily": "Switches and Hubs"}]

        result = dnac.template_programmer.update_template(id=self.templateid, name=self.name,deviceTypes=devicetypes,
                                                    softwareType="IOS-XE",
                                                          templateContent=body)
        logger.debug(result)
        task = wait_for_task(dnac, result.response.taskId)

        logger.debug(json.dumps(task))
        if not task.isError:
            # commit
            print("Commiting {}".format(task.response.data))
            response = dnac.template_programmer.version_template(templateId=task.response.data)
            logging.debug('version {}'.format(json.dumps(response)))
        else:
            print("FAILED: {}".format(task.response.progress))

    def upload(self, body):
        # create new template

        devicetypes = [{"productFamily": "Switches and Hubs"} ]

        result = dnac.template_programmer.create_template(name=self.name, project_id=self.projectId,  deviceTypes=devicetypes,
                                                    softwareType="IOS-XE", templateContent=body)
        logger.debug(result)
        task = wait_for_task(dnac, result.response.taskId)
        logger.debug(json.dumps(task))
        if not task.isError:
            # commit
            print("Commiting {}".format(task.response.data))
            response = dnac.template_programmer.version_template(templateId=task.response.data)
            logging.debug('version {}'.format(json.dumps(response)))
        else:
            print ("FAILED: {}".format(task.response.progress))
        # commit

    def delete(self):
        # delele template
        pass

    def _get_project_id(self):
        projects = self.dnac.template_programmer.get_projects(name="Onboarding Configuration")
        logger.debug("Projects:{}, {}".format(projects, projects[0]))
        return projects[0].id

    def present(self):
        # find template
        logger.debug("projectId:{}".format(self.projectId))
        templates = dnac.template_programmer.gets_the_templates_available(projectid=self.projectId)
        for template in templates:
            logger.debug(template.name)
            if template.name == self.name:
                logger.debug("template:{}".format(template))
                self.templateid = template.templateId
                # the versions are also present. The latest version is the toplevel template id.
                t = dnac.template_programmer.get_template_details(template_id = self.templateid)
                logger.debug ("body:{}".format(t.templateContent))
                return get_sha1(t.templateContent)

        logger.debug("template {} not found".format(self.name))
        return None

def upload_templates(dnac, rootDir):
    if not os.path.isdir(rootDir):
        print("No directory for {rootDir}, skipping".format(rootDir=rootDir))
        return

    for filename in os.listdir(rootDir):
        print("Processing:{}: ".format(filename),end='')
        with open(rootDir + "/" + filename) as f:
            content = f.read()
        logger.debug("new content:{}".format(content))
        newsha = get_sha1(content)
        logger.debug("SHA:{}".format(newsha))
        t = Template(dnac, filename)
        currentsha = t.present()
        if currentsha is None:
            print("adding NEW:", end='')
            t.upload(content)
        elif currentsha != newsha:
            print("updating:", end='')
            t.update(content)
        else:
            print("No update required")

if __name__ == "__main__":
    parser = ArgumentParser(description='Select options.')
    parser.add_argument('--dir', type=str, required=True,
                        help="directory to load configs from ")
    parser.add_argument('-v', action='store_true',
                        help="verbose")
    args = parser.parse_args()

    if args.v:
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.debug("logging enabled")

    dnac =api.DNACenterAPI()

    upload_templates(dnac, args.dir)