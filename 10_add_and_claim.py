#!/usr/bin/env python
from __future__ import print_function
import json
import requests
import time
# turn off warninggs
requests.packages.urllib3.disable_warnings()

import logging
import csv
from argparse import ArgumentParser
from dnacentersdk import api, exceptions

# create a logger
logger = logging.getLogger(__name__)

class TaskTimeoutError(Exception):
    pass

class TaskError(Exception):
    pass

class SiteCache:
    def __init__(self, dnac):
        self._cache = {}
        self.dnac = dnac
    def lookup(self, sitename):
        if sitename in self._cache:
            return self._cache[sitename]
        else:
            # cant use name and type together?
            #lookup = self.dnac.sites.get_site(name=sitename, type="building")
            try:
                lookup = self.dnac.sites.get_site(name=sitename)
            except exceptions.ApiError:
                raise ValueError("Cannot find site:{}".format(sitename))
            logger.debug("sitecache:{}".format(lookup))
            if lookup.response[0]:
                self._cache[sitename] = lookup.response[0].id
                return self._cache[sitename]
            else:
                raise ValueError("Cannot find site:{}".format(sitename))

class ImageCache:
    def __init__(self, dnac):
        self._cache = {}
        self.dnac = dnac
    def lookup(self, imagename):
        if imagename in self._cache:
            return self._cache[imagename]
        else:
            lookup = self.dnac.swim.get_software_image_details(name=imagename)
            logging.debug("imagecache:{}".format(lookup))
            if lookup.response != []:
                self._cache[imagename] = lookup.response[0].imageUuid
                return self._cache[imagename]
            else:
                raise ValueError("Cannot find image:{}".format(imagename))

class TemplateCache:
    def __init__(self, dnac):
        self._cache = {}
        self.dnac = dnac
        # going to prime this one, as no lookup by name
        projects = self.dnac.template_programmer.get_projects(name="Onboarding Configuration")
        for template in projects[0].templates:
            self._cache[template.name] = template.id
    def lookup(self, templatename):
        if templatename in self._cache:
            return self._cache[templatename]
        else:
            raise ValueError("Cannot find template:{}".format(templatename))

def add_device(dnac, name, serial, pid, top_of_stack):
    if top_of_stack is None:
        stack = False
    else:
        stack = True
    payload = [{
	"deviceInfo": {
		"hostname": name,
		"serialNumber": serial,
		"pid": pid,
		"sudiRequired": False,
		"userSudiSerialNos": [],
		"stack": stack,
		"aaaCredentials": {
			"username": "",
			"password": ""
		}
	}
}]
    logger.debug(json.dumps(payload))
    device = dnac.pnp.import_devices_in_bulk(payload=payload)
    try:
        deviceId = device.successList[0].id
    except IndexError as e:
        print ('##SKIPPING device:{},{}:{}'.format(name, serial, device.failureList[0].msg))
        deviceId = None

    return deviceId

def claim_device(dnac,deviceId, configId, siteId, top_of_stack, imageId):

    payload = {
        "siteId": siteId,
         "deviceId": deviceId,
         "type": "Default",
         "imageInfo": {"imageId": imageId, "skip": False},
         "configInfo": {"configId": configId, "configParameters": []}
}
    if top_of_stack is not None:
        payload['type'] = "StackSwitch"
        payload['topOfStackSerialNumber'] = top_of_stack
    logger.debug(json.dumps(payload, indent=2))

    claim = dnac.pnp.claim_a_device_to_a_site(payload=payload)
    return claim.response

def add_and_claim(dnac, template_cache, image_cache, site_cache, devices):
    f = open(devices, 'rt')
    try:
        reader = csv.DictReader(f)
        for device_row in reader:
            logging.debug ("Variables:",device_row)

            try:
                siteId = site_cache.lookup(device_row['siteName'])
                #image is optional
                if 'image' in device_row and device_row['image'] != '':
                    imageId = image_cache.lookup(device_row['image'])
                else:
                    imageId = ''
                templateId = template_cache.lookup(device_row['template'])
            except ValueError as e:
                print("##ERROR {},{}: {}".format(device_row['name'],device_row['serial'], e))
                continue

            if 'topOfStack' in device_row:
                top_of_stack = device_row['topOfStack']
            else:
                top_of_stack = None

            # add device to PnP
            deviceId = add_device(dnac, device_row['name'], device_row['serial'], device_row['pid'], top_of_stack)
            if deviceId is not None:
                #claim the device if sucessfully added
                claim_status = claim_device(dnac, deviceId, templateId, siteId, top_of_stack, imageId)
                if "Claimed" in claim_status:
                    status = "PLANNED"
                else:
                    status = "FAILED"
                print ('Device:{} name:{} siteName:{} Status:{}'.format(device_row['serial'],
                                                                    device_row['name'],
                                                                    device_row['siteName'],
                                                                    status))
    finally:
        f.close()

if __name__ == "__main__":
    parser = ArgumentParser(description='Select options.')
    parser.add_argument('--file', type=str, required=True,
                        help="load from file")
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
    template_cache = TemplateCache(dnac)
    image_cache = ImageCache(dnac)
    site_cache = SiteCache(dnac)
    add_and_claim(dnac, template_cache, image_cache, site_cache, args.file)