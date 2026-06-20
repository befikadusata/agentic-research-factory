import yaml
import os

def load_prompts():
    config_path = os.path.join(os.path.dirname(__file__), "prompts.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)["agent_prompts"]

prompts = load_prompts()

def get_prompt(agent_name: str):
    return prompts.get(agent_name)
