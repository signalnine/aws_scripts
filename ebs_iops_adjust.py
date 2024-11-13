import boto3
import argparse

def get_instance_name(instance_tags):
    if instance_tags:
        for tag in instance_tags:
            if tag['Key'] == 'Name':
                return tag['Value']
    return 'N/A'

# Parse the command-line arguments
parser = argparse.ArgumentParser(description='Change the provisioned IOPS and throughput for EBS volumes attached to EC2 instances with a specific tag.')
parser.add_argument('--iops', type=int, required=True, help='The new provisioned IOPS value')
parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
parser.add_argument('--apply', action='store_true', help='Apply the changes (default: dry run)')
parser.add_argument('--tag-key', required=True, help='The instance tag key to filter by')
parser.add_argument('--tag-value', required=True, help='The instance tag value to filter by')
parser.add_argument('--volume-type', required=True, choices=['io1', 'io2', 'gp3'], help='The EBS volume type to modify (e.g., io1, io2, gp3)')
args = parser.parse_args()

# Set up boto3 clients with the specified region
ec2 = boto3.resource('ec2', region_name=args.region)
client = boto3.client('ec2', region_name=args.region)

# Filter the instances with the specific tag
instances = ec2.instances.filter(
    Filters=[
        {
            'Name': f'tag:{args.tag_key}',
            'Values': [args.tag_value]
        }
    ]
)

# Set the desired IOPS value
new_iops = args.iops
new_throughput = int(new_iops * 0.25) if args.volume_type == 'gp3' else None

# Iterate through instances and modify the EBS volumes' IOPS and throughput
for instance in instances:
    instance_name = get_instance_name(instance.tags)
    for device in instance.block_device_mappings:
        volume_id = device['Ebs']['VolumeId']
        volume = ec2.Volume(volume_id)
        volume_type = volume.volume_type

        if volume_type == args.volume_type:
            current_iops = volume.iops
            current_throughput = volume.throughput if volume_type == 'gp3' else None

            if current_iops == new_iops and (volume_type != 'gp3' or current_throughput == new_throughput):
                print(f"Skipping volume {volume_id} attached to instance {instance.id} ({instance_name}): IOPS and throughput already set to desired values")
            else:
                print(f"Current IOPS for volume {volume_id} attached to instance {instance.id} ({instance_name}): {current_iops}")
                if volume_type == 'gp3':
                    print(f"Current throughput for volume {volume_id} attached to instance {instance_name}: {current_throughput} MiBps")

                if args.apply:
                    print(f"Modifying IOPS for volume {volume_id} attached to instance {instance.id} ({instance_name})")
                    modify_params = {
                        'VolumeId': volume_id,
                        'Iops': new_iops
                    }
                    if volume_type == 'gp3':
                        modify_params['Throughput'] = new_throughput
                    client.modify_volume(**modify_params)
                else:
                    print(f"Dry run: Would change IOPS for volume {volume_id} attached to instance {instance.id} ({instance_name}) from {current_iops} to {new_iops}")
                    if volume_type == 'gp3':
                        print(f"Dry run: Would change throughput for volume {volume_id} attached to instance {instance_name} from {current_throughput} MiBps to {new_throughput} MiBps")
        else:
            print(f"Skipping volume {volume_id} of type {volume_type} attached to instance {instance.id} ({instance_name})")

if args.apply:
    print("EBS volumes IOPS and throughput modification complete.")
else:
    print("Dry run complete. Use --apply flag to modify the IOPS and throughput.")
