import boto3

# Connect to EC2
ec2 = boto3.client('ec2')

# Get all instances with retirement notices
reservations = ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}, {'Name': 'retirement', 'Values': ['notified']}])['Reservations']

if reservations:
    # Loop through the instances and print information about each one
    for reservation in reservations:
        instance = reservation['Instances'][0]

        # Get the instance name from the tags
        instance_name = [tag['Value'] for tag in instance['Tags'] if tag['Key'] == 'Name'][0]

        retirement = instance['InstanceLifecycle']
        retirement_status = retirement.get('Status')
        retirement_message = retirement.get('Message')

        print(f"Instance Name: {instance_name}")
        print(f"Instance ID: {instance['InstanceId']}")
        print(f"Retirement Status: {retirement_status}")
        print(f"Retirement Message: {retirement_message}")
        print("-----")
else:
    print("There are no instance retirement notices.")

