import boto3
import sys
import yaml
import requests
import argparse

# Load instance pricing information from the provided YAML file
def load_instance_prices(yaml_url):
    response = requests.get(yaml_url, verify=False)
    yaml_data = yaml.safe_load(response.text)
    instance_prices = {}

    for instance_type, instance_info in yaml_data.items():
        if "Linux" in instance_info["prices"]:
            linux_prices = instance_info["prices"]["Linux"]
            if "us-east-1" in linux_prices:
                price = linux_prices["us-east-1"]["Shared"]
                instance_prices[instance_type] = price

    return instance_prices


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Estimate AWS EC2 monthly costs based on running instances.")
    parser.add_argument("-t", "--tag", nargs="+", metavar=("KEY=VALUE"),
                        help="Filter instances by tag key-value pairs. Can be used multiple times for different tags.")
    return parser.parse_args()


def get_running_instances(tags):
    ec2 = boto3.resource("ec2")
    filters = [{"Name": "instance-state-name", "Values": ["running"]}]
    if tags:
        tag_filters = []
        for tag in tags:
            key, value = tag.split("=")
            tag_filters.append({"Name": f"tag:{key}", "Values": [value]})
        # Add all tag filters as a single "AND" filter
        for tag_filter in tag_filters:
            filters.append(tag_filter)
    instances = ec2.instances.filter(Filters=filters)
    return instances


def estimate_ec2_monthly_cost(instance, instance_prices):
    instance_type = instance.instance_type
    if instance_type in instance_prices:
        return instance_prices[instance_type] * 24 * 30
    else:
        print(
            f"Error: Instance type {instance_type} not found in instance_prices.", file=sys.stderr)
        return 0


def estimate_rds_monthly_cost(instance, rds_prices):
    instance_class = instance['DBInstanceClass']
    if instance_class in rds_prices:
        return rds_prices[instance_class] * 24 * 30
    else:
        print(
            f"Error: Instance class {instance_class} not found in rds_prices.", file=sys.stderr)
        return 0


def load_rds_prices(db_instance_class):
    rds_prices = {}

    client = boto3.client("pricing", region_name="us-east-1")
    response = client.get_products(
        Filters=[
            {
                "Field": "instanceType",
                "Type": "TERM_MATCH",
                "Value": db_instance_class,
            },
        ],
        ServiceCode="AmazonRDS",
        FormatVersion="aws_v1",
        MaxResults=1,
    )

    for price in response["PriceList"]:
        price_data = yaml.safe_load(price)
        term = price_data["terms"]["OnDemand"]
        term_attributes = term[next(iter(term))]["priceDimensions"][next(
            iter(term[next(iter(term))]["priceDimensions"]))]
        rds_prices[db_instance_class] = float(
            term_attributes["pricePerUnit"]["USD"])

    return rds_prices


def get_running_rds_instances(tags=None):
    rds = boto3.client("rds")
    response = rds.describe_db_instances()
    instances = [instance for instance in response['DBInstances']
                 if instance['DBInstanceStatus'] == 'available']

    if tags:
        filtered_instances = []
        for instance in instances:
            for tag_info in instance['TagList']:
                for tag in tags:
                    key, value = tag.split('=')
                    if tag_info['Key'] == key and tag_info['Value'] == value:
                        filtered_instances.append(instance)
                        break
        instances = filtered_instances

    return instances


def get_ebs_prices():
    return {
        "gp2": 0.10,  # General Purpose SSD (gp2)
        "gp3": 0.08,  # General Purpose SSD (gp3)
        "io1": 0.125,  # Provisioned IOPS SSD (io1)
        "io2": 0.15,  # Provisioned IOPS SSD (io2)
        "st1": 0.045,  # Throughput Optimized HDD (st1)
        "sc1": 0.025,  # Cold HDD (sc1)
        "standard": 0.05,  # Magnetic (standard)
    }


def estimate_ebs_volume_cost(volume, ebs_prices):
    volume_type = volume.volume_type
    size = volume.size

    if volume_type in ebs_prices:
        return ebs_prices[volume_type] * size / 30
    else:
        print(
            f"Error: Volume type {volume_type} not found in ebs_prices.", file=sys.stderr)
        return 0


def main():
    args = parse_arguments()
    yaml_url = "https://tedivm.github.io/ec2details/api/ec2instances.yaml"
    instance_prices = load_instance_prices(yaml_url)
    ebs_prices = get_ebs_prices()

    ec2_running_instances = get_running_instances(args.tag)
    rds_running_instances = get_running_rds_instances(args.tag)

    ec2_total_monthly_cost = 0
    ec2_costs_by_instance_type = {}
    rds_total_monthly_cost = 0
    rds_costs_by_instance_type = {}

    # EC2 instances
    for instance in ec2_running_instances:
        instance_cost = estimate_ec2_monthly_cost(instance, instance_prices)
        print(
            f"EC2 Instance {instance.id} ({instance.instance_type}): ${instance_cost:.2f} per month")
        ec2_total_monthly_cost += instance_cost

        if instance.instance_type not in ec2_costs_by_instance_type:
            ec2_costs_by_instance_type[instance.instance_type] = 0
        ec2_costs_by_instance_type[instance.instance_type] += instance_cost

        # Calculate EBS volume costs
        for volume in instance.volumes.all():
            ebs_cost = estimate_ebs_volume_cost(volume, ebs_prices)
            print(
                f"  EBS Volume {volume.id} ({volume.volume_type}, {volume.size} GiB): ${ebs_cost:.2f} per month")
            ec2_total_monthly_cost += ebs_cost

    print("\nEC2 Costs by instance type:")
    for instance_type, cost in ec2_costs_by_instance_type.items():
        print(f"{instance_type}: ${cost:.2f}")
    print(
        f"\nTotal estimated monthly cost for all running EC2 instances and EBS volumes: ${ec2_total_monthly_cost:.2f}\n")

    # RDS instances
    rds_prices = {}
    for instance in rds_running_instances:
        if instance['DBInstanceClass'] not in rds_prices:
            rds_prices[instance['DBInstanceClass']] = load_rds_prices(
                instance['DBInstanceClass'])[instance['DBInstanceClass']]

        instance_cost = estimate_rds_monthly_cost(instance, rds_prices)

        print(
            f"RDS Instance {instance['DBInstanceIdentifier']} ({instance['DBInstanceClass']}): ${instance_cost:.2f} per month")
        rds_total_monthly_cost += instance_cost

        if instance['DBInstanceClass'] not in rds_costs_by_instance_type:
            rds_costs_by_instance_type[instance['DBInstanceClass']] = 0
        rds_costs_by_instance_type[instance['DBInstanceClass']
                                   ] += instance_cost

    print("\nRDS Costs by instance type:")
    for instance_type, cost in rds_costs_by_instance_type.items():
        print(f"{instance_type}: ${cost:.2f}")
    print(
        f"\nTotal estimated monthly cost for all running RDS instances: ${rds_total_monthly_cost:.2f}\n")

    print(
        f"Overall Total estimated monthly cost: ${ec2_total_monthly_cost + rds_total_monthly_cost:.2f}")


if __name__ == "__main__":
    main()
