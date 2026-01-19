curl -X 'POST' \
'http://localhost:8000/graph/mutations' \
-H 'accept: application/json' \
-H 'Content-Type: application/jsonlines' \
--data-binary "@/home/jsell/Downloads/master_ontology_FULL (3).jsonl"


# curl -X 'POST' \
# 'http://localhost:8000/graph/mutations' \
# -H 'accept: application/json' \
# -H 'Content-Type: application/jsonlines' \
# --data-binary @/home/jsell/output-graph.jsonl
