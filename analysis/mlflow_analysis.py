from collections import defaultdict
import sys
import json
import mlflow
import os
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

mlflow.set_tracking_uri("sqlite:///../mlflow.db")

client = InferenceClient(
    provider="hf-inference",
    api_key=os.environ["HF_TOKEN"],
)

experiment_ids = [exp.experiment_id for exp in mlflow.search_experiments()]
opinion_traces = mlflow.search_traces(experiment_ids=experiment_ids)
opinion_graph = defaultdict(lambda: defaultdict(list))

for t in tqdm(opinion_traces["trace_id"].tolist()):
    trace = mlflow.get_trace(t)
    span = trace.data.spans[0]
    
    if not "old_summary" in span.inputs:
        continue
    if span.outputs is None or not "new_summary" in span.outputs:
        continue
    
    username = span.inputs["self_user"]["username"]
    target = span.inputs["target_username"]
    old_summary = span.inputs["old_summary"]
    new_summary = span.outputs["new_summary"]
    
    result = client.text_classification(
        new_summary[:1500].rstrip() + ("..." if len(new_summary) > 1500 else ""),
        model="SamLowe/roberta-base-go_emotions",
    )
    
    opinion_graph[username][target].append({out.label: out.score for out in result})

with open("opinion_graph.json", "w") as f:
    json.dump(opinion_graph, f, indent=4)