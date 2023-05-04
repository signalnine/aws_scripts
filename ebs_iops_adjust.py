import boto3
import argparse

def get_instance_name(instance_tags):
    for tag in instance_tags:
        if tag['Key'] == 'Name':
            return tag['Value']
    return 'N/A'

# Parse the command-line arguments
parser = argparse.ArgumentParser(description='Change the provisioned IOPS and throughput for EBS volumes attached to EC2 instances with a specific tag.')
parser.add_argument('--iops', type=int, required=True, help='The new provisioned IOPS value')
parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
parser.add_argument('--apply', action='store_true', help='Apply the changes (default: dry run)')
args = parser.parse_args()

# Set up boto3 clients with the specified region
ec2 = boto3.resource('ec2', region_name=args.region)
client = boto3.client('ec2', region_name=args.region)

# Set the desired tag key-value pair
tag_key = 'Service'
tag_value = 'ecs_cluster'

# Set the desired IOPS value
new_iops = args.iops
new_throughput = int(new_iops * 0.25)

# Filter the instances with the specific tag
instances = ec2.instances.filter(
    Filters=[
        {
            'Name': 'tag:' + tag_key,
            'Values': [tag_value]
        }
    ]
)

# Iterate through instances and modify the EBS volumes' IOPS and throughput
for instance in instances:
    instance_name = get_instance_name(instance.tags)
    for device in instance.block_device_mappings:
        volume_id = device['Ebs']['VolumeId']
        volume = ec2.Volume(volume_id)
        volume_type = volume.volume_type

        if volume_type in ['io1', 'io2', 'gp3']:
            current_iops = volume.iops
            if volume_type == 'gp3':
                current_throughput = volume.throughput

            if current_iops == new_iops and (volume_type != 'gp3' or current_throughput == new_throughput):
                print(f"Skipping volume {volume_id} attached to instance {instance.id} ({instance_name}): IOPS and throughput already set to desired values")
            else:
                print(f"Current IOPS for volume {volume_id} attached to instance {instance.id} ({instance_name}): {current_iops}")
                if volume_type == 'gp3':
                    print(f"Current throughput for volume {volume_id} attached to instance {instance.id} ({instance_name}): {current_throughput} MiBps")

                if args.apply:
                    print(f"Modifying IOPS for volume {volume_id} attached to instance {instance.id} ({instance_name})")
                    if volume_type == 'gp3':
                        print(f"Modifying throughput for volume {volume_id} attached to instance {instance.id} ({instance_name})")
                        client.modify_volume(
                            VolumeId=volume_id,
                            Iops=new_iops,
                            Throughput=new_throughput
                        )
                    else:
                        client.modify_volume(
                            VolumeId=volume_id,
                            Iops=new_iops
                        )
                else:
                    print(f"Dry run: Would change IOPS for volume {volume_id} attached to instance {instance.id} ({instance_name}) from {current_iops} to {new_iops}")
                    if volume_type == 'gp3':
                        print(f"Dry run: Would change throughput for volume {volume_id} attached to instance {instance.id} ({instance_name}) from {current_throughput} MiBps to {new_throughput} MiBps")
        else:
            print(f"Skipping volume {volume_id} of type {volume_type} attached to instance {instance.id} ({instance_name})")

if args.apply:
    print("EBS volumes IOPS and throughput modification complete.")
else:
    print("Dry run complete. Use --apply flag to modify the IOPS and throughput.")
