from elasticsearch import Elasticsearch


class ESQueries(object):

    query_failures = {"query": {"query_string": {"query": "build_status:FAILURE AND message:\"Finished: FAILURE\""}}, "_cache": True}
    query_success = {"query": {"query_string": {"query": "build_status:SUCCESS AND message:\"Finished: SUCCESS\""}}, "_cache": True}
    query_all_constraints = {"query": {"query_string": {"query": "build_name:*-constraints"}}, "_cache": True}
    query_master = {"query": {"query_string": {"query": "build_branch:\"master\""}}, "_cache": True}

    def __init__(self):
        self.es = Elasticsearch('http://logstash.openstack.org:80/elasticsearch/', timeout=90)
        self.query_project = {"query": {"query_string": {"query": "project:\"openstack/neutron\""}}, "_cache": True}

    def get_failed_job(self, build_change, build_name, build_patchset):
        query_build_name = {"query": {"query_string": {"query": "build_name:\"%s\"" % build_name}}, "_cache": True}
        query_build_patchset = {"query": {"query_string": {"query": "build_patchset:%s" % build_patchset}}, "_cache": True}
        jsn = self.es.search(index='_all',
            body={
                "query": {
                    "filtered": {
                        "query": {
                            "bool": {
                                "should": [
                                    {"query_string": {"query": ("build_change:%s" % build_change)}}
                                ]
                            }
                        },
                    "filter": {
                        "bool": {
                            "must": [
                                {"fquery": query_build_name},
                                {"fquery": query_build_patchset},
                                {"fquery": self.query_failures},
                                {"fquery": self.query_project}
                            ]
                        }
                    }
                }
            },
            "size": 50,
        })
        return jsn

    def get_successful_job(self, build_change, build_name, build_patchset):
        query_build_name = {"query": {"query_string": {"query": "build_name:\"%s\"" % build_name}}, "_cache": True}
        query_build_patchset = {"query": {"query_string": {"query": "build_patchset:%s" % build_patchset}}, "_cache": True}
        jsn = self.es.search(index='_all',
            body={
                "query": {
                    "filtered": {
                        "query": {
                            "bool": {
                                "should": [
                                    {"query_string": {"query": ("build_change:%s" % build_change)}}
                                ]
                            }
                        },
                    "filter": {
                        "bool": {
                            "must": [
                                {"fquery": query_build_name},
                                {"fquery": query_build_patchset},
                                {"fquery": self.query_success},
                                {"fquery": self.query_project}
                            ]
                        }
                    }
                }
            },
            "size": 50,
        })
        return jsn

    def get_failed_constraints_changes(self, index, project):
        jsn = self.es.search(
            index='_all',
            body={"facets": {"terms": {
                "terms": {
                    "field": "build_change",
                    "size": 99999,
                    "order": "term",
                    "exclude": []
                },
                "facet_filter": {"fquery": {"query": {"filtered": {
                    "query": {"bool": {"should": [{
                            "query_string": {"query": "project:\"openstack/neutron\""}
                        }]}},
                        "filter": {"bool": {"must": [
                            {"fquery": self.query_master},
                            {"fquery": self.query_all_constraints},
                            {"fquery": self.query_failures}
                        ]}}
                    }}}}
                }},
                "size": 0
            }
        )
        return jsn

    def enumerate_constraints_failures(self, build_change):
        jsn = self.es.search(index='_all',
            body={
                "query": {
                    "filtered": {
                        "query": {
                            "bool": {
                                "should": [
                                    {
                                        "query_string": {
                                            "query": ("build_change:%s" % build_change)
                                        }
                                    }
                                ]
                            }
                        },
                    "filter": {
                        "bool": {
                            "must": [
                                {"fquery": self.query_project},
                                {"fquery": self.query_all_constraints},
                                {"fquery": self.query_failures}
                            ]
                        }
                    }
                }
            },
            "size": 50,
        })
        return jsn


class JobManager(object):

    def __init__(self, change_num):
        self.change_number = change_num
        self.patch_list = {}
        self.possible_bad_runs = []

    def add_item(self, name, status, log, patchset):
        if name not in self.patch_list:
            self.patch_list[name] = {}
        if patchset not in self.patch_list[name]:
            self.patch_list[name][patchset] = []
        self.patch_list[name][patchset].append((status, log))

    def check_for_possible_failures(self):
        esq = ESQueries()
        for name in self.patch_list.keys():
            for patchset in self.patch_list[name].keys():
                success_json = esq.get_successful_job(self.change_number, name, patchset)
                success = 0
                failed_json = esq.get_failed_job(self.change_number, name, patchset)
                failed = 0
                for hit in success_json['hits']['hits']:
                    if isinstance(hit['_source']['build_change'], list):
                        for index in range(len(hit['_source']['build_change'])):
                            if hit['_source']['build_change'][index] == self.change_number:
                                if hit['_source']['build_status'][index] == "SUCCESS":
                                    success += 1
                    else:
                        success += 1
                for hit in failed_json['hits']['hits']:
                    if isinstance(hit['_source']['build_change'], list):
                        for index in range(len(hit['_source']['build_change'])):
                            if hit['_source']['build_change'][index] == self.change_number:
                                if hit['_source']['build_status'][index] == "FAILURE":
                                    failed += 1
                    else:
                        failed += 1
                unsuccess_json = esq.get_successful_job(self.change_number, name[0:-12], patchset)
                unsuccess = 0
                unfailed_json = esq.get_failed_job(self.change_number, name[0:-12], patchset)
                unfailed = 0
                for hit in unsuccess_json['hits']['hits']:
                    if isinstance(hit['_source']['build_change'], list):
                        for index in range(len(hit['_source']['build_change'])):
                            if hit['_source']['build_change'][index] == self.change_number:
                                if hit['_source']['build_status'][index] == "SUCCESS":
                                    unsuccess += 1
                    else:
                        unsuccess += 1
                for hit in unfailed_json['hits']['hits']:
                    if isinstance(hit['_source']['build_change'], list):
                        for index in range(len(hit['_source']['build_change'])):
                            if hit['_source']['build_change'][index] == self.change_number:
                                if hit['_source']['build_status'][index] == "FAILURE":
                                    unfailed += 1
                    else:
                        unfailed += 1
                if failed > unfailed:
                    self.possible_bad_runs.append("%s: Found passing unconstrained complmenting a failed constraint - NAME: %s -- PATCHSET: %s" % (self.change_number, name, patchset))
                elif failed > 0 and not failed == unfailed:
                    self.possible_bad_runs.append("%s: Found possible passing recheck - NAME: %s -- PATCHSET: %s" % (self.change_number, name, patchset))
                # TODO: Get log check for known false positives?


class ChangeManager(object):

    def __init__(self):
        self.unprocessed_changes = set()
        self.changes = {}
        self.succeeds = 0
        self.failed = 0

    def add_change(self, change):
        if change in self.changes:
            return
        self.unprocessed_changes.add(change)

    def process_changes(self):
        for change in self.unprocessed_changes:
            self.get_all_jobs_and_parse(change)
        self.unprocessed_changes.clear()
        for change in self.changes.keys():
            self.changes[change].check_for_possible_failures()

    def get_all_jobs_and_parse(self, change_number):
        esq = ESQueries()
        es_json = esq.enumerate_constraints_failures(change_number)
        for hit in es_json['hits']['hits']:
            if isinstance(hit['_source']['build_change'], list):
                for index in range(len(hit['_source']['build_change'])):
                    if hit['_source']['build_change'][index] == change_number:
                        name, status, log, patchset = self.get_values(hit, index)
            else:
                name, status, log, patchset = self.get_values(hit, None)
            if not name or not status or not log or not patchset:
                self.failed += 1
                continue
            if status == "FAILURE" and hit['_source']['build_change'] == change_number:
                if change_number not in self.changes:
                    self.changes[change_number] = JobManager(change_number)
                self.changes[change_number].add_item(name, status, log, patchset)
            self.succeeds += 1

    def get_value(self, json, key, index):
        if not isinstance(json[key], list):
            return json[key]
        elif index is not None:
            try:
                return json[key][index]
            except IndexError:
                return None
        else:
            return None

    def get_values(self, hit_json, index):
        hit_json = hit_json['_source']
        name = self.get_value(hit_json, 'build_name', index)
        status = self.get_value(hit_json, 'build_status', index)
        log = self.get_value(hit_json, 'log_url', index)
        patchset = self.get_value(hit_json, 'build_patchset', index)
        return name, status, log, patchset

esq = ESQueries()

cm = ChangeManager()


def cli():
    for term in esq.get_failed_constraints_changes('a', 'b')['facets']['terms']['terms']:
        cm.add_change(term["term"])
    cm.process_changes()
    print("Processed %i changes" % cm.succeeds)
    print("Failed to parse %i changes" % cm.failed)
    for change in cm.changes:
        for msg in cm.changes[change].possible_bad_runs:
            print(msg)

if __name__ == "__main__":
    cli()

# for breakpoint
pass
