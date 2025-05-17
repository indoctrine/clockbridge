"""
AUTHOR:     Beck D.
DATE:       2023-
PURPOSE:    This module handles pushing data to Elasticsearch
"""

import json
from datetime import datetime
import sys
import logging
import requests
import urllib3

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    stream=sys.stderr,level=logging.INFO)

class Elastic:
    """Elastic class"""
    def __init__(self, config):
        self.base_url = config['url']
        self.index_prefix = config['index_prefix']
        self.index = self.index_prefix
        self.user = config['username']
        self.pwd = config['password'].decode().strip()
        self.hc_url = f"{self.base_url}_cluster/health"
        self.insecure = config['insecure']
        if self.insecure:
            urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)

    def health_check(self, timeout=50):
        """Health check the Elastic endpoint"""
        health = requests.get(
            self.hc_url,
            auth=(self.user, self.pwd),
            verify=not self.insecure,
            headers={"Content-Type": "application/json"},
            timeout=50
            )

        logging.info("Elasticsearch health check returned %s", health.json()['status'])
        return(health.ok and health.json()['status'] == "green")

    def gen_index_date(self, end_date):
        """Generate the <prefix>-YYYY-MM name for the index"""
        dt_end = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S%z")
        self.index = f"{self.index_prefix}-{dt_end.strftime('%Y-%m')}"

    def delete_doc(self, data, action="delete"):
        """Delete document in Elastic by document ID"""
        try:
            self.gen_index_date(data['timeInterval']['end'])
            r = requests.delete(f"{self.base_url}{self.index}/_doc/{data['id']}",
                            auth=(self.user, self.pwd),
                            verify=not self.insecure,
                            headers={"Content-Type": "application/json"},
                            timeout=10
                        )
            if r.ok:
                logging.info("Deleted existing document from Elasticsearch:\n %s", r.content)
                return True

            if r.status_code == 404 and action == "update":
                logging.info("Document does not currently exist, but will be created by update action")
                return True

            raise requests.exceptions.HTTPError(r.content)
        except Exception as e:
            logging.exception("Unable to delete document from Elasticsearch\n %s", e)

    def create_doc(self, data):
        """Create document in Elastic with custom document ID from payload"""
        try:
            self.gen_index_date(data['timeInterval']['end'])
            r = requests.post(f"{self.base_url}{self.index}/_create/{data['id']}",
                            data=json.dumps(data),
                            auth=(self.user, self.pwd),
                            verify=not self.insecure,
                            headers={"Content-Type": "application/json"},
                            timeout=10
                        )
            if r.ok:
                logging.info("Created new document in Elasticsearch:\n %s", r.content)
                return True

            raise requests.exceptions.HTTPError(r.content)
        except Exception as e:
            logging.exception("Unable to create document in Elasticsearch\n %s", e)
            return False

    def update_doc(self, data):
        """Update document in Elastic by deleting the document and recreating it with the new data"""
        try:
            self.delete_doc(data, "update")
            self.create_doc(data)
            return True

        except Exception as e:
            logging.exception("Unable to update document in Elasticsearch\n %s", e)
            return False
