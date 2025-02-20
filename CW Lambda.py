fetch logs
| filter log.source == "apigee"
| filter k8s.deployment.name in ("app_id_1", "app_id_2", "app_id_3", "app_id_4")
| parse content, "IPD: *" as apigee_proxy
| parse content, "URI: *" as apigee_uri
| parse content, "HTTP_STATUS: *" as http_status
| fields apigee_proxy, apigee_uri, http_status
| filter http_status >= 400
| summarize failure_count = count(), total_requests = count(), by apigee_proxy, apigee_uri
| fieldsAdd failure_rate = (failure_count / total_requests) * 100
| filter failure_rate > 5
| sort failure_rate desc