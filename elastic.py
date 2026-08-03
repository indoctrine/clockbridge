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

    def push(self, data, action="create"):
        """
        Submit a single entry to Elasticsearch endpoint by action verb.

        action is one of "create", "update" or "delete"; any other value
        falls back to "create". Returns the underlying method's result.
        """
        if action == "delete":
            return self.delete_doc(data)
        if action == "update":
            return self.update_doc(data)
        return self.create_doc(data)

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
                logging.info("Document does not exist, but will be created by update action")
                return True

            raise requests.exceptions.HTTPError(r.content)
        except Exception as e:
            logging.exception("Unable to delete document from Elasticsearch\n %s", e)
            return False

    def create_doc(self, data):
        """
        Create document in Elastic with custom document ID from payload
        """
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

    def _search(self, body):
        r = requests.post(f"{self.base_url}{self.index_prefix}-*/_search",
                          data=json.dumps(body),
                          auth=(self.user, self.pwd),
                          verify=not self.insecure,
                          headers={"Content-Type": "application/json"},
                          timeout=10)
        r.raise_for_status()
        return r.json()

    def recent_entries(self, limit=10, offset=0):
        """Return the most recent completed entries across all monthly indices."""
        body = {
            "size": limit,
            "from": offset,
            "sort": [{"timeInterval.end": {"order": "desc"}}],
            "_source": ["id", "description", "project", "projectId",
                        "task", "timeInterval", "@timestamp"],
        }
        hits = self._search(body).get("hits", {}).get("hits", [])
        return [h["_source"] for h in hits]

    def distinct_clients(self):
        """Distinct (clientId, clientName) pairs seen in indexed entries."""
        body = {
            "size": 0,
            "query": {"exists": {"field": "project.clientId"}},
            "aggs": {"clients": {"multi_terms": {"terms": [
                {"field": "project.clientId.keyword"},
                {"field": "project.clientName.keyword"},
            ], "size": 200}}},
        }
        buckets = self._search(body).get("aggregations", {}) \
                                    .get("clients", {}).get("buckets", [])
        return [{"clientId": b["key"][0], "clientName": b["key"][1]} for b in buckets]

    def distinct_projects(self, client_id=None):
        """Distinct projects; optionally scoped to a client."""
        filters = [{"exists": {"field": "projectId"}}]
        if client_id:
            filters.append({"term": {"project.clientId.keyword": client_id}})
        body = {
            "size": 0,
            "query": {"bool": {"filter": filters}},
            "aggs": {"projects": {"multi_terms": {"terms": [
                {"field": "projectId.keyword"},
                {"field": "project.name.keyword"},
                {"field": "project.clientId.keyword"},
                {"field": "project.clientName.keyword"},
            ], "size": 500}}},
        }
        buckets = self._search(body).get("aggregations", {}) \
                                    .get("projects", {}).get("buckets", [])
        return [{"projectId": b["key"][0], "name": b["key"][1],
                 "clientId": b["key"][2], "clientName": b["key"][3]}
                for b in buckets]

    def distinct_tasks(self, project_id=None):
        """Distinct task names; optionally scoped to a project."""
        filters = [{"exists": {"field": "task.name"}}]
        if project_id:
            filters.append({"term": {"projectId.keyword": project_id}})
        body = {
            "size": 0,
            "query": {"bool": {"filter": filters}},
            "aggs": {"tasks": {"terms": {"field": "task.name.keyword", "size": 500}}},
        }
        buckets = self._search(body).get("aggregations", {}) \
                                    .get("tasks", {}).get("buckets", [])
        return [{"name": b["key"]} for b in buckets]

    def update_doc(self, data):
        """
        Update document in Elastic by deleting the document and recreating it 
        with the new data, selected by ID
        """
        try:
            self.delete_doc(data, "update")
            self.create_doc(data)
            return True

        except Exception as e:
            logging.exception("Unable to update document in Elasticsearch\n %s", e)
            return False
