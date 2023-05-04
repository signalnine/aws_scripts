import boto3
import sys
import yaml
import requests

# Load instance pricing information from the provided YAML file
def load_instance_prices(yaml_url):
    response = requests.get(yaml_url)
    yaml_data = yaml.safe_load(response.text)
    instance_prices = {}

    for instance_type, instance_info in yaml_data.items():
        if "Linux" in instance_info["prices"]:
            linux_prices = instance_info["prices"]["Linux"]
            if "us-east-1" in linux_prices:
                price = linux_prices["us-east-1"]["Shared"]
                instance_prices[instance_type] = price

    return instance_prices

def get_running_instances():
    ec2 = boto3.resource("ec2")
    instances = ec2.instances.filter(Filters=[{"Name": "instance-state-name", "Values": ["running"]}])
    return instances

def estimate_monthly_cost(instance, instance_prices):
    instance_type = instance.instance_type
    if instance_type in instance_prices:
        return instance_prices[instance_type] * 24 * 30
    else:
        print(f"Error: Instance type {instance_type} not found in instance_prices.", file=sys.stderr)
        return 0

def main():
    yaml_url = "https://tedivm.github.io/ec2details/api/ec2instances.yaml"
    instance_prices = load_instance_prices(yaml_url)

    running_instances = get_running_instances()
    total_monthly_cost = 0
    costs_by_instance_type = {}

    for instance in running_instances:
        instance_cost = estimate_monthly_cost(instance, instance_prices)
        print(f"Instance {instance.id} ({instance.instance_type}): ${instance_cost:.2f} per month")
        total_monthly_cost += instance_cost

        if instance.instance_type not in costs_by_instance_type:
            costs_by_instance_type[instance.instance_type] = 0
        costs_by_instance_type[instance.instance_type] += instance_cost

    print("\nCosts by instance type:")
    for instance_type, cost in costs_by_instance_type.items():
        print(f"{instance_type}: ${cost:.2f}")

    print(f"\nTotal estimated monthly cost for all running instances: ${total_monthly_cost:.2f}")

if __name__ == "__main__":
    main()
